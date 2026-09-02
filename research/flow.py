#!/usr/bin/env python3
# VERSION: 2026-09-02-f1
"""
flow.py -- the order book, streamed. Does order flow predict the next move?

    python research/flow.py --selftest
    python research/flow.py --data ./kalshi_data --out ./fulltape

WHY THIS, AND WHY NOW

Every question this project has asked so far has been a question about PRICE:
is the price wrong, is the implied volatility wrong, is the calibration
rotated. Six of them are now dead, and the last one -- volatility -- died
cleanly: `a` sits at 1.01-1.17 across seven taus, six of seven confidence
intervals contain 1, and the walk-forward is negative in six of eight series.
The price is not wrong in any way we have been able to measure.

`orderbook_delta` is 395,685,479 messages, about twenty times the rest of the
tape put together, and it has never been read. `book.py` reaches it, but the
depth number the project actually uses comes from `depth_from_ticker` -- a
shortcut over the `ticker` channel -- because a full rebuild wanted ~30 GB on
a 16 GB machine. So the largest thing on disk is, in practice, untouched.

It also asks a DIFFERENT question. Not "is the price wrong" but "does the
order flow know, one second early, where the price is going". That is a
microstructure question, it has a large literature, and it is the one
question left that the tape can answer and we have not asked.

MEMORY: WHY THIS IS A STREAM AND NOT A REBUILD

`book.py` holds every orderbook message in RAM so it can sort them. That is
the 30 GB. It does not need to: within one collector file the messages are
already in arrival order, so a k-way merge across files yields a globally
time-ordered stream in memory proportional to the NUMBER OF FILES, not the
number of messages. Book state is then proportional to the number of markets
alive at once, which for 15-minute contracts is a handful.

The output is one row per (market, second) -- not per message -- so 395
million messages become a few million rows, written once, cached per day, and
re-analysed in seconds.

WHAT IS MEASURED

  x   ORDER FLOW IMBALANCE over the second (t-1, t], the Cont-Kukanov-Stoikov
      level-1 construction: size added at the bid minus size pulled from it,
      minus size added at the ask plus size pulled from it.
  y   the change in the mid from the END of second t to the end of second t+k.

x is complete before y begins. Nothing in x is measured after the mid it is
asked to predict -- which is the single easiest way to manufacture this exact
result, and the reason the split is drawn at a second boundary rather than a
message boundary.

THE GRID IS EXOGENOUS

A second in which nothing happened is still a second. Sampling only the
seconds that carry messages selects on activity, and activity is correlated
with movement, so the sample would be built out of exactly the moments the
answer is about. Every second in the window is emitted, message or not, with
the book carried forward -- which is what the book actually was, since Kalshi
sends a delta only when something changes.

Forward-fill is bounded by a GLOBAL clock: a second is emitted only if some
message, on any market, was seen at or after it. Otherwise a dead collector
would be recorded as a calm market.

THE NULLS

  1. cluster-robust on close time, G = closes, and the MDE printed BEFORE the
     estimate, so "no effect" and "no power" cannot be confused.
  2. a TIME-SHIFTED placebo: the same x against a y 300 seconds away in the
     same market. Real flow, wrong moment. It must read zero.
  3. a BACKWARD check: x against the move that has ALREADY happened. This one
     must be strongly positive -- flow follows price mechanically -- and it is
     here to prove the sign convention and the wiring, because a forward
     result of zero is uninformative if the code cannot find an effect that
     must be there.
  4. money, out of sample: beta fitted on the first half of the tape, traded
     on the second half, paying the real spread and the real quadratic fee
     both ways. A slope significantly different from zero is not an edge; it
     is only an edge if it clears the cost of crossing.
"""

import argparse
import glob
import gzip
import json
import math
import os
import random
import shutil
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from heapq import merge
from statistics import mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gzsalvage import iter_lines as salvage_lines          # noqa: E402
from book import Book, _levels, _cents, _resolve_ob        # noqa: E402
from engine import fee_per_contract                        # noqa: E402


def t_crit(df):
    return _tcrit(0.05, df)
from tdist import crit as _tcrit                           # noqa: E402

P_LO, P_HI = 0.05, 0.95     # a mid outside this is on the tapered tick grid
MIN_LEAD = 30               # seconds before close where mining stops
TAU_MAX = 900               # seconds before close where mining starts
MAX_FILL = 300              # never carry a book forward more than this


# ===========================================================================
# THE STREAM
# ===========================================================================
def _file_stream(fp, fi):
    """(rx_seconds, file_index, line_index, message) for one collector file.

    Already in arrival order on disk -- the collector appends -- so this is a
    sorted input and `merge` can do the rest without holding anything.
    """
    i = 0
    for line in salvage_lines(fp):
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        i += 1
        rx = m.get("_rx_ms")
        if isinstance(rx, (int, float)):
            t = rx / 1000.0
        else:
            d = m.get("msg") or {}
            t = _ts(d.get("ts")) or 0.0
        yield (t, fi, i, m)


def _ts(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v if v < 1e12 else v / 1000.0)
    try:
        return datetime.fromisoformat(
            str(v).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _first_time(fp):
    for line in salvage_lines(fp):
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        rx = m.get("_rx_ms")
        if isinstance(rx, (int, float)):
            return rx / 1000.0
        return _ts((m.get("msg") or {}).get("ts"))
    return None


def ob_files(data_dir):
    """Both orderbook channels, grouped by the UTC day of their first message.

    Grouped by day so the mine can cache and resume. A day boundary costs the
    first few seconds of book validity on each market alive across it, until
    Kalshi's next snapshot -- against re-reading 3.6 GB to add one day, which
    is the difference between a stage that can be re-run and one that cannot.
    """
    files = []
    for ch in ("orderbook_snapshot", "orderbook_delta"):
        files += glob.glob(os.path.join(data_dir, ch, "*.jsonl.gz"))
    by_day = defaultdict(list)
    for fp in sorted(files):
        t = _first_time(fp)
        if t is None:
            continue
        day = datetime.fromtimestamp(t, timezone.utc).strftime("%Y%m%d")
        by_day[day].append(fp)
    return dict(sorted(by_day.items()))


# ===========================================================================
# ORDER FLOW IMBALANCE
# ===========================================================================
def ofi_step(old, new):
    """Cont-Kukanov-Stoikov level-1 order flow imbalance for one book change.

    old/new are (bid_price, bid_size, ask_price, ask_size) in integer cents
    and contracts. Either may be None -- an empty or invalid book contributes
    nothing and resets the chain rather than contributing a fiction.

    The construction, in words: size arriving at the bid is buying pressure,
    size leaving it is selling pressure, and a bid that MOVES counts its whole
    new level as arrival and the whole old one as departure. The ask is the
    same with the signs flipped. It is deliberately blind to trades vs
    cancels, because the tape cannot tell them apart and the literature finds
    it does not need to.
    """
    if old is None or new is None:
        return None
    bp0, bs0, ap0, as0 = old
    bp1, bs1, ap1, as1 = new
    e = 0.0
    if bp1 >= bp0:
        e += bs1
    if bp1 <= bp0:
        e -= bs0
    if ap1 <= ap0:
        e -= as1
    if ap1 >= ap0:
        e += as0
    return e


def _l1(bk):
    """(bid_cents, bid_size, ask_cents, ask_size) or None.

    The ask is the best NO bid reflected: bidding p for NO is offering YES at
    100 - p. Anything that reads only the `yes` map is looking at half the
    market -- and does not error, it just quietly halves the view.
    """
    if not bk.valid or not bk.yes or not bk.no:
        return None
    yb = max(bk.yes)
    nb = max(bk.no)
    ya = 100 - nb
    if not (0 < yb < ya < 100):
        return None
    return (yb, bk.yes[yb], ya, bk.no[nb])


# ===========================================================================
# THE MINE
# ===========================================================================
def mine_day(files, windows, verbose=False, max_msgs=None):
    """One day of both orderbook channels -> rows, in bounded memory.

    `windows` is ticker -> (start_sec, end_sec): the only seconds worth
    emitting. Everything else is applied to the book and dropped, so the
    output is proportional to the markets we can actually score rather than
    to the tape.

    A row is:
        (ticker, sec, bid_c, ask_c, bid_sz, ask_sz, ofi, nmsg, dbid, dask)
    with prices in integer cents, the book state as of the END of `sec`, and
    `ofi` accumulated over the messages that arrived DURING `sec`.
    """
    stats = defaultdict(int)
    rows = []
    if not files:
        return rows, stats

    sample = []
    for fp in files:
        for line in salvage_lines(fp):
            try:
                sample.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(sample) >= 2000:
                break
        if len(sample) >= 2000:
            break
    scale = _resolve_ob(sample)["scale"]
    stats["scale"] = scale

    books = defaultdict(Book)
    sid_tk = defaultdict(set)      # subscription -> the tickers under it
    sid_seq = {}
    last_l1 = {}                   # ticker -> l1 after the previous message
    cur = {}                       # ticker -> (sec being accumulated, ofi, n)
    live = {}                      # ticker -> (start, end) for tickers in play
    gclock = 0

    def emit(tk, sec, ofi, n):
        bk = books.get(tk)
        l1 = _l1(bk) if bk is not None else None
        if l1 is None:
            stats["sec_invalid"] += 1
            return
        b, bs, a, as_ = l1
        db, da = bk.depth_within(3)
        rows.append((tk, sec, b, a, bs, as_, ofi, n,
                     db if db is not None else 0.0,
                     da if da is not None else 0.0))

    def flush(tk, upto):
        """Emit every second strictly before `upto` that we owe for `tk`."""
        st = cur.get(tk)
        if st is None:
            return
        sec, ofi, n = st
        w = live.get(tk)
        if w is None:
            cur.pop(tk, None)
            return
        s0, s1 = w
        stop = min(upto, s1 + 1, sec + MAX_FILL + 1)
        s = sec
        while s < stop:
            if s0 <= s <= s1:
                emit(tk, s, ofi if s == sec else 0.0, n if s == sec else 0)
            s += 1
        if s >= s1 + 1:
            cur.pop(tk, None)         # window is finished with
            live.pop(tk, None)
            books.pop(tk, None)
            last_l1.pop(tk, None)
        else:
            cur[tk] = (max(s, upto), 0.0, 0)

    def sweep(now):
        """Carry every live market forward to the global clock."""
        for tk in list(cur):
            flush(tk, now)

    streams = [_file_stream(fp, i) for i, fp in enumerate(files)]
    n_read = 0
    for t, _fi, _li, m in merge(*streams):
        n_read += 1
        if max_msgs and n_read > max_msgs:
            break
        typ = m.get("type", "")
        is_snap = "orderbook_snapshot" in typ
        if not (is_snap or "orderbook_delta" in typ):
            continue
        d = m.get("msg") or {}
        tk = d.get("market_ticker") or d.get("ticker")
        if not tk:
            stats["no_ticker"] += 1
            continue

        # SEQUENCE FIRST, BEFORE ANY FILTER. seq counts every message in the
        # subscription, including the thousands of tickers we have no
        # settlement for and the ones whose window has closed. Skipping those
        # for efficiency and then testing continuity reads a hole in OUR
        # sample as a hole in KALSHI's stream, and invalidates every book we
        # hold, forever. This is the same class of mistake as keying
        # continuity on the ticker, which once left 24 of 1,090 markets
        # standing -- and it would have been invisible here, because the
        # self-test fixture has one ticker per subscription unless it is
        # built not to.
        sid = m.get("sid")
        sid = tk if sid is None else sid
        seq = m.get("seq")
        if not isinstance(seq, int):
            seq = (d.get("seq") if isinstance(d.get("seq"), int) else None)
        if isinstance(seq, int):
            prev = sid_seq.get(sid)
            if prev is not None and seq != prev + 1:
                # A gap is a property of the SUBSCRIPTION, not of the message
                # that revealed it: every book under that sid is fiction from
                # here until it gets a fresh snapshot.
                for other in sid_tk[sid]:
                    b2 = books.get(other)
                    if b2 is not None and b2.valid:
                        b2.valid = False
                        last_l1.pop(other, None)
                        stats["seq_gaps"] += 1
            sid_seq[sid] = seq

        w = windows.get(tk)
        if w is None:
            stats["no_settlement"] += 1
            continue
        sec = int(t)
        if sec > gclock:
            gclock = sec
            sweep(gclock)
        if sec > w[1]:
            continue                  # past this market's window entirely
        sid_tk[sid].add(tk)

        bk = books[tk]
        if is_snap:
            bk.snapshot(_levels(d.get("yes"), scale),
                        _levels(d.get("no"), scale), seq, t)
            stats["snapshots"] += 1
            last_l1.pop(tk, None)     # a reset is not a flow event
        else:
            side = str(d.get("side") or d.get("taker") or "").lower()
            price = _cents(d.get("price_dollars", d.get("price")), scale)
            chg = d.get("delta_fp", d.get("delta", d.get("change")))
            try:
                chg = float(chg)
            except (TypeError, ValueError):
                chg = None
            if price is None or chg is None or side not in ("yes", "no"):
                stats["unparsed_delta"] += 1
                continue
            if not bk.valid:
                stats["delta_while_invalid"] += 1
                continue
            bk.apply(price, chg, side, t)
            stats["deltas"] += 1

        if sec < w[0]:
            continue                  # before the window: book state only

        new = _l1(bk)
        e = ofi_step(last_l1.get(tk), new)
        last_l1[tk] = new

        if tk not in live:
            live[tk] = w
        st = cur.get(tk)
        if st is None:
            cur[tk] = (sec, e or 0.0, 1)
        elif st[0] == sec:
            cur[tk] = (sec, st[1] + (e or 0.0), st[2] + 1)
        else:
            flush(tk, sec)
            cur[tk] = (sec, e or 0.0, 1)

    sweep(gclock + 1)
    for tk in list(cur):
        flush(tk, gclock + 1)
    stats["rows"] = len(rows)
    stats["messages"] = n_read
    return rows, stats


def windows_from_markets(markets, tau=TAU_MAX, lead=MIN_LEAD):
    w = {}
    for tk, m in markets.items():
        c = m.get("close")
        if c is None:
            continue
        c = int(round(float(c)))
        w[tk] = (c - tau, c - lead)
    return w


CACHE_HDR = "ticker,sec,bid_c,ask_c,bid_sz,ask_sz,ofi,nmsg,dbid,dask\n"


def mine(data_dir, markets, cache_dir, verbose=True, rebuild=False,
         max_msgs=None, tau=TAU_MAX):
    """Mine every day, caching per day. Returns the cache paths."""
    os.makedirs(cache_dir, exist_ok=True)
    windows = windows_from_markets(markets, tau=tau)
    days = ob_files(data_dir)
    if verbose:
        print(f"  flow: {len(days)} day(s) of orderbook files, "
              f"{sum(len(v) for v in days.values())} files, "
              f"{len(windows):,} markets with a settlement")
    paths = []
    for day, files in days.items():
        fp = os.path.join(cache_dir, f"{day}.csv.gz")
        if os.path.exists(fp) and not rebuild:
            paths.append(fp)
            if verbose:
                print(f"    {day}: cached")
            continue
        rows, st = mine_day(files, windows, verbose=verbose, max_msgs=max_msgs)
        tmp = fp + ".part"
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            f.write(CACHE_HDR)
            for r in rows:
                f.write("%s,%d,%d,%d,%.2f,%.2f,%.4f,%d,%.2f,%.2f\n" % r)
        os.replace(tmp, fp)
        paths.append(fp)
        if verbose:
            print(f"    {day}: {st['rows']:,} rows from "
                  f"{st['messages']:,} messages  "
                  f"(deltas {st['deltas']:,}, snapshots {st['snapshots']:,}, "
                  f"seq gaps {st['seq_gaps']:,}, "
                  f"unparsed {st['unparsed_delta']:,})")
            if st["deltas"] == 0 and st["messages"] > 1000:
                print("    *** every delta unparsed -- the field names moved. "
                      "This is exactly how the channel came back empty before.")
    return paths


def load_rows(paths, markets, verbose=True):
    """ticker -> {sec: (bid_c, ask_c, ofi)}.

    THREE fields, not the ten in the cache. At five million market-seconds
    every extra float in the tuple is a 120 MB tax, and the sizes and depths
    are not in the regression -- they are summarised straight off the file by
    `book_summary`, which streams and holds nothing. Prices stay integer
    cents on purpose: CPython caches small ints, so 1..99 costs no allocation
    at all, while the same numbers as floats cost 24 bytes each, ten million
    times over.
    """
    out = defaultdict(dict)
    n = 0
    for fp in paths:
        with gzip.open(fp, "rt", encoding="utf-8") as f:
            head = f.readline()
            if not head.startswith("ticker,"):
                continue
            for line in f:
                p = line.rstrip("\n").split(",")
                if len(p) != 10:
                    continue
                try:
                    out[p[0]][int(p[1])] = (int(p[2]), int(p[3]), float(p[6]))
                    n += 1
                except ValueError:
                    continue
    if verbose:
        print(f"  flow: {n:,} market-seconds over {len(out):,} markets")
    return dict(out)


def book_summary(paths, verbose=True):
    """Spread and resting depth, streamed off the cache, holding nothing.

    This is the number PLAN sec.4 hangs the maker verdict on. It went
    taker-only because a REST orderbook call reported "best bid 0.40 with
    3,767 contracts resting" -- and RUNBOOK separately records that the same
    REST endpoint returns levels ASCENDING and truncates from the BOTTOM,
    which hid top-of-book. A number read off an endpoint that was
    simultaneously mis-parsed deserves re-measurement from the websocket
    stream before it is allowed to kill a strategy. Here it is, from the
    stream, on every market-second we have.
    """
    spreads, touch, near = [], [], []
    n = 0
    for fp in paths:
        with gzip.open(fp, "rt", encoding="utf-8") as f:
            if not f.readline().startswith("ticker,"):
                continue
            for line in f:
                p = line.rstrip("\n").split(",")
                if len(p) != 10:
                    continue
                try:
                    b, a = int(p[2]), int(p[3])
                    bs, as_ = float(p[4]), float(p[5])
                    db, da = float(p[8]), float(p[9])
                except ValueError:
                    continue
                n += 1
                spreads.append(a - b)
                touch.append((bs + as_) / 2.0)
                near.append((db + da) / 2.0)
    if not n:
        return None
    spreads.sort(); touch.sort(); near.sort()

    def q(v, f):
        return v[min(len(v) - 1, int(f * len(v)))]
    r = {"n": n,
         "spread": (q(spreads, .25), q(spreads, .5), q(spreads, .75)),
         "touch": (q(touch, .25), q(touch, .5), q(touch, .75)),
         "near3": (q(near, .25), q(near, .5), q(near, .75))}
    if verbose:
        print("\n" + "=" * 78)
        print("WHAT THE BOOK ACTUALLY LOOKS LIKE, from the websocket stream")
        print("=" * 78)
        print(f"  {n:,} market-seconds, quartiles (25th / median / 75th)")
        print(f"    spread, cents                 "
              f"{r['spread'][0]:>8.0f} {r['spread'][1]:>8.0f} "
              f"{r['spread'][2]:>8.0f}")
        print(f"    contracts AT the touch        "
              f"{r['touch'][0]:>8.0f} {r['touch'][1]:>8.0f} "
              f"{r['touch'][2]:>8.0f}")
        print(f"    contracts within 3 cents      "
              f"{r['near3'][0]:>8.0f} {r['near3'][1]:>8.0f} "
              f"{r['near3'][2]:>8.0f}")
        print("\n  A resting quote has to outlast the contracts already in")
        print("  front of it. That queue is the maker verdict, and this is")
        print("  the first time it has been read off the stream rather than")
        print("  off the REST endpoint that RUNBOOK records as mis-parsed.")
    return r


# ===========================================================================
# THE MEASUREMENT
# ===========================================================================
def pairs(rows, markets, k, shift=0, backward=False, tau=TAU_MAX):
    """(close, x, y) per usable second.

    x is the OFI accumulated during second t; y is the mid move in CENTS from
    the end of second t to the end of second t+k. `shift` moves the RESPONSE
    away in time inside the same market -- real flow against an unrelated
    moment, which is the placebo. `backward` asks x against the move that has
    already finished, which must be strongly positive if the wiring is right.
    """
    out = []
    for tk, bysec in rows.items():
        m = markets.get(tk)
        if not m or m.get("close") is None:
            continue
        close = int(round(float(m["close"])))
        for sec, r in bysec.items():
            b, a = r[0], r[1]
            mid0 = (b + a) / 2.0
            if not (P_LO * 100 <= mid0 <= P_HI * 100):
                continue
            if backward:
                s2 = sec - k
                nxt = bysec.get(s2)
                if nxt is None:
                    continue
                mid1 = (nxt[0] + nxt[1]) / 2.0
                y = mid0 - mid1
            else:
                s2 = sec + k + shift
                nxt = bysec.get(s2)
                if nxt is None:
                    continue
                base = bysec.get(sec + shift) if shift else r
                if base is None:
                    continue
                mid_b = (base[0] + base[1]) / 2.0
                mid1 = (nxt[0] + nxt[1]) / 2.0
                y = mid1 - mid_b
            out.append((close, r[2], y, b, a))
    return out


def ols_cluster(obs):
    """Slope of y on x with an intercept, CR0 clustered on close time.

    n is CLOSES. Rows are seconds inside a market and are autocorrelated to a
    degree that makes an iid standard error pure decoration; the closes are
    the independent unit here, exactly as everywhere else in this project.
    """
    n = len(obs)
    if n < 100:
        return None
    xs = [o[1] for o in obs]
    ys = [o[2] for o in obs]
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx

    byc = defaultdict(list)
    for o in obs:
        byc[o[0]].append(o)
    G = len(byc)
    if G < 5:
        return None

    def se_with(slope, inter):
        meat = 0.0
        for c in byc.values():
            s = sum((o[1] - mx) * (o[2] - inter - slope * o[1]) for o in c)
            meat += s * s
        meat *= G / (G - 1.0)          # finite-cluster correction
        return math.sqrt(meat) / sxx

    se = se_with(b, a)
    se0 = se_with(0.0, my)             # under the null: pre-fit, for the MDE
    tc = t_crit(G - 1)
    return {"b": b, "se": se, "t": (b / se if se > 0 else 0.0),
            "mde": tc * se0, "n": n, "G": G,
            "sd_x": pstdev(xs) if n > 1 else 0.0,
            "sd_y": pstdev(ys) if n > 1 else 0.0}


def show(tag, r):
    if r is None:
        print(f"    {tag:<34} not enough data")
        return
    flag = "" if abs(r["b"]) > r["mde"] else "   INSIDE THE MDE"
    print(f"    {tag:<34} {r['b']:+8.4f}c  t={r['t']:+6.2f}  "
          f"MDE {r['mde']:.4f}c  G={r['G']:,}  n={r['n']:,}{flag}")


# ===========================================================================
# MONEY, OUT OF SAMPLE
# ===========================================================================
def trade_oos(obs, k, verbose=True):
    """Fit the slope on the first half of the tape, trade the second half.

    A slope that differs from zero is not an edge. Crossing costs the spread
    and a quadratic fee at BOTH ends, so the predicted move has to clear
    roughly a whole spread plus two fees before a taker sees a cent of it.
    """
    if len(obs) < 500:
        return None
    closes = sorted({o[0] for o in obs})
    if len(closes) < 20:
        return None
    cut = closes[len(closes) // 2]
    tr = [o for o in obs if o[0] < cut]
    te = [o for o in obs if o[0] >= cut]
    f = ols_cluster(tr)
    if f is None or not te:
        return None
    b = f["b"]

    trades = []
    for close, x, y, bid, ask in te:
        pred = b * x
        # Enter at the touch and exit at the OPPOSITE touch k seconds later.
        # Buying at the ask and selling at the bid costs a full spread, not a
        # half, and Kalshi's quadratic taker fee is paid at both ends. A
        # forecast worth less than that is worth nothing.
        fees = 100.0 * (fee_per_contract(ask / 100.0) +
                        fee_per_contract(bid / 100.0))
        cost = (ask - bid) + fees
        if pred > cost:
            trades.append((close, y - cost))        # long YES
        elif pred < -cost:
            trades.append((close, -y - cost))       # short YES = long NO
    if len(trades) < 30:
        return {"b_train": b, "trades": len(trades), "mean": None}
    byc = defaultdict(list)
    for c, p in trades:
        byc[c].append(p)
    G = len(byc)
    per = [mean(v) for v in byc.values()]
    mu = mean(per)
    if G < 5:
        return {"b_train": b, "trades": len(trades), "mean": mu}
    sd = pstdev(per) * math.sqrt(G / (G - 1.0))
    se = sd / math.sqrt(G)
    return {"b_train": b, "trades": len(trades), "mean": mu, "G": G,
            "t": mu / se if se > 0 else 0.0, "mde": t_crit(G - 1) * se}


# ===========================================================================
# SELF-TEST
# ===========================================================================
def _write_feed(root, spec, seed=7, predictive=True, drop_seq=False):
    """A synthetic collector directory in the REAL layout: two channels, two
    directories, one file each, prices as `price_dollars`, sizes as
    `delta_fp`. A fixture that disagrees with the collector tests nothing --
    this project has shipped that bug twice.

    The planted world: a latent d_t per second. Size lands at the bid when
    d_t > 0 and at the ask when d_t < 0, so OFI ~ d_t; and if `predictive`,
    the mid moves by d_t on the NEXT second. If not, the mid moves on an
    independent draw and the flow is real but tells you nothing.
    """
    rnd = random.Random(seed)
    snap_dir = os.path.join(root, "orderbook_snapshot")
    delt_dir = os.path.join(root, "orderbook_delta")
    os.makedirs(snap_dir, exist_ok=True)
    os.makedirs(delt_dir, exist_ok=True)
    msgs = []
    markets = {}

    def nxt():
        return None      # seq is assigned in ARRIVAL order, at the end

    for tk, close, mid0 in spec:
        markets[tk] = {"ticker": tk, "close": close, "strike": 1.0,
                       "result": 1.0}
        # A LADDER, not one level a side. With a single level, a price step
        # deletes the only level, the side goes momentarily empty, `_l1`
        # returns None and the OFI chain resets -- so the reactive flow that
        # every real move generates contributes exactly nothing, and the
        # backward check reads zero on a fixture where it must be enormous.
        # Real Kalshi books are several levels deep and never do this.
        DEPTH, LOT = 5, 400.0
        bid, ask = mid0 - 1, mid0 + 1
        t0 = close - TAU_MAX
        yes = {bid - i: LOT for i in range(DEPTH)}
        no = {(100 - ask) - i: LOT for i in range(DEPTH)}
        msgs.append({"type": "orderbook_snapshot", "sid": 1, "seq": nxt(),
                     "_rx_ms": int(t0 * 1000),
                     "msg": {"market_ticker": tk,
                             "yes": [[b / 100.0, sz] for b, sz in yes.items()],
                             "no": [[q / 100.0, sz] for q, sz in no.items()]}})

        def d_msg(sec_ms, side, price_c, delta, book):
            msgs.append({"type": "orderbook_delta", "sid": 1, "seq": nxt(),
                         "_rx_ms": sec_ms,
                         "msg": {"market_ticker": tk, "side": side,
                                 "price_dollars": price_c / 100.0,
                                 "delta_fp": delta}})
            book[price_c] = book.get(price_c, 0.0) + delta
            if book[price_c] <= 0:
                book.pop(price_c, None)

        pend = 0
        for sec in range(t0 + 1, close - MIN_LEAD):
            # THE STEP DECIDED LAST SECOND LANDS NOW. This is the whole point
            # of the fixture and it was wrong the first time: with the step
            # inside the same second as the flow that predicts it, the planted
            # effect is CONTEMPORANEOUS, the forward regression is correctly
            # zero, and the fixture tests the opposite of what it claims. The
            # backward check caught it -- t = +340 backward on a forward
            # reading of zero is not a null result, it is a fixture bug
            # wearing one.
            if pend and 8 < bid + pend and ask + pend < 92:
                t1 = int(sec * 1000) + 100
                if pend > 0:
                    d_msg(t1, "yes", bid + 1, LOT, yes)              # new bid
                    d_msg(t1 + 1, "yes", bid - DEPTH + 1,
                          -yes.get(bid - DEPTH + 1, 0.0), yes)
                    d_msg(t1 + 2, "no", 100 - ask,
                          -no.get(100 - ask, 0.0), no)               # ask up
                    d_msg(t1 + 3, "no", 100 - ask - DEPTH, LOT, no)
                else:
                    d_msg(t1, "no", 100 - ask + 1, LOT, no)          # ask down
                    d_msg(t1 + 1, "no", 100 - ask - DEPTH + 1,
                          -no.get(100 - ask - DEPTH + 1, 0.0), no)
                    d_msg(t1 + 2, "yes", bid, -yes.get(bid, 0.0), yes)
                    d_msg(t1 + 3, "yes", bid - DEPTH, LOT, yes)
                bid, ask = bid + pend, ask + pend
            pend = 0

            d = rnd.gauss(0, 1)
            add = round(abs(d) * 60.0, 2) + 1.0
            if d > 0:
                d_msg(int(sec * 1000) + 200, "yes", bid, add, yes)
            else:
                d_msg(int(sec * 1000) + 200, "no", 100 - ask, add, no)
            # the move is decided now and lands NEXT second, so x is complete
            # before the y it is asked to predict has begun
            move = d if predictive else rnd.gauss(0, 1)
            pend = 1 if move > 0.6 else (-1 if move < -0.6 else 0)

    # SEQ IN ARRIVAL ORDER, ACROSS BOTH CHANNELS AND EVERY TICKER. Kalshi
    # increments one counter per subscription as it sends, so a fixture that
    # numbers market-by-market hands the reader a stream whose seq jumps
    # backwards on every interleave -- which the reader correctly calls a gap,
    # correctly invalidates every book, and correctly emits nothing. The
    # fixture was wrong and the reader was right, which is the single hardest
    # failure in this project to read off the output.
    msgs.sort(key=lambda z: z["_rx_ms"])
    for i, m in enumerate(msgs, start=1):
        m["seq"] = i
    if drop_seq:
        dd = [i for i, m in enumerate(msgs) if "delta" in m["type"]]
        del msgs[dd[len(dd) // 2]]

    snaps = [m for m in msgs if "snapshot" in m["type"]]
    delts = [m for m in msgs if "delta" in m["type"]]
    for fp, part in ((os.path.join(snap_dir, "a.jsonl.gz"), snaps),
                     (os.path.join(delt_dir, "a.jsonl.gz"), delts)):
        with gzip.open(fp, "wt", encoding="utf-8") as f:
            for m in part:
                f.write(json.dumps(m) + "\n")
    return markets


def _spec(n_close, per_close, base=1767225600, seed=1):
    rnd = random.Random(seed)
    out = []
    for c in range(n_close):
        close = base + c * 900
        for j in range(per_close):
            out.append((f"KXTEST-{c}-{j}", close,
                        rnd.choice([30, 40, 50, 60, 70])))
    return out


def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []
    tmp = tempfile.mkdtemp(prefix="flow_")
    try:
        # -- 1. a world where flow REALLY predicts the next move ------------
        print("\n  A planted world: size lands on the side the price is about")
        print("  to move toward. The miner must find it, and the placebo and")
        print("  the backward check must behave.")
        spec = _spec(40, 2, seed=3)
        d1 = os.path.join(tmp, "yes")
        mk = _write_feed(d1, spec, seed=3, predictive=True)
        paths = mine(d1, mk, os.path.join(tmp, "c1"), verbose=False)
        rows = load_rows(paths, mk, verbose=False)
        nrows = sum(len(v) for v in rows.values())
        print(f"    mined {nrows:,} market-seconds over {len(rows)} markets")
        if nrows < 1000:
            fails.append(f"the mine produced {nrows} market-seconds -- the "
                         "fixture is in the collector's layout, so this is "
                         "the reader, not the fixture")
        fwd = ols_cluster(pairs(rows, mk, k=1))
        show("forward, k=1", fwd)
        if fwd is None or fwd["t"] < 4:
            fails.append("the miner cannot find an effect that was planted -- "
                         "a null result from this code would mean nothing")
        pla = ols_cluster(pairs(rows, mk, k=1, shift=300))
        show("placebo, y shifted +300s", pla)
        if pla is not None and abs(pla["b"]) > pla["mde"]:
            fails.append(f"the placebo read {pla['b']:+.4f}c, outside its own "
                         f"MDE {pla['mde']:.4f}c -- real flow against an "
                         "unrelated moment must read zero")
        bwd = ols_cluster(pairs(rows, mk, k=1, backward=True))
        show("backward (must be positive)", bwd)
        if bwd is None or bwd["t"] < 10:
            fails.append("the backward check is not strongly positive -- "
                         "flow follows price mechanically, so a forward zero "
                         "from this wiring would be uninterpretable")

        _, h = mine_day(sorted(glob.glob(os.path.join(d1, "*", "*.gz"))),
                        windows_from_markets(mk), verbose=False)
        print(f"    healthy feed: seq gaps {h['seq_gaps']}, deltas applied "
              f"while invalid {h['delta_while_invalid']}, "
              f"unparsed {h['unparsed_delta']}")
        if h["seq_gaps"] or h["delta_while_invalid"] or h["unparsed_delta"]:
            fails.append("an intact feed produced gaps or unparsed deltas -- "
                         "the reader is inventing holes, and on real data "
                         "that silently discards the channel")

        mny = trade_oos(pairs(rows, mk, k=1), 1)
        print(f"    money block runs: {mny is not None}")
        if mny is None:
            fails.append("trade_oos returned nothing on 69k rows")

        bs = book_summary(paths, verbose=False)
        print(f"    book summary: median spread {bs['spread'][1]:.0f}c, "
              f"{bs['touch'][1]:.0f} at the touch, "
              f"{bs['near3'][1]:.0f} within 3c")
        if bs is None or bs["spread"][1] != 2:
            fails.append("the book summary does not recover the fixture's "
                         "known 2-cent spread")

        # -- 2. exogenous grid: quiet seconds must still be there -----------
        gaps = 0
        for tk, bysec in rows.items():
            ss = sorted(bysec)
            gaps += sum(1 for i in range(1, len(ss)) if ss[i] - ss[i - 1] > 1)
        print(f"\n  Exogenous grid: {gaps} holes in {len(rows)} markets' "
              "second-by-second coverage")
        if gaps > len(rows):
            fails.append(f"{gaps} holes -- seconds without a message are being "
                         "dropped, which samples on activity")

        # -- 3. a world where the flow is real and tells you NOTHING --------
        print("\n  A world where the flow is just as loud but the price moves")
        print("  on an independent draw. The answer must be nothing.")
        d2 = os.path.join(tmp, "no")
        mk2 = _write_feed(d2, _spec(40, 2, seed=5), seed=5, predictive=False)
        rows2 = load_rows(mine(d2, mk2, os.path.join(tmp, "c2"),
                               verbose=False), mk2, verbose=False)
        nul = ols_cluster(pairs(rows2, mk2, k=1))
        show("forward, k=1 (calibrated)", nul)
        if nul is not None and abs(nul["b"]) > nul["mde"]:
            fails.append(f"an unpredictable market read {nul['b']:+.4f}c "
                         f"against an MDE of {nul['mde']:.4f}c -- the "
                         "estimator manufactures an effect")

        # -- 4. a sequence gap must invalidate, not silently corrupt --------
        print("\n  One delta deleted mid-stream. The book under that")
        print("  subscription must go invalid, not carry on being wrong.")
        d3 = os.path.join(tmp, "gap")
        mk3 = _write_feed(d3, _spec(6, 1, seed=9), seed=9, drop_seq=True)
        _, st = mine_day(sorted(glob.glob(os.path.join(d3, "*", "*.gz"))),
                         windows_from_markets(mk3), verbose=False)
        print(f"    seq gaps caught: {st['seq_gaps']:,}, "
              f"deltas applied while invalid: {st['delta_while_invalid']:,}")
        if st["seq_gaps"] == 0:
            fails.append("a deleted message produced no sequence gap -- "
                         "deltas are being applied across a hole, and every "
                         "level after it is fiction")

        # -- 5. the cache must be a cache, not a second opinion -------------
        again = load_rows(mine(d1, mk, os.path.join(tmp, "c1"), verbose=False),
                          mk, verbose=False)
        same = (sum(len(v) for v in again.values()) == nrows)
        print(f"\n  Re-run off the cache reproduces the same "
              f"{nrows:,} rows: {same}")
        if not same:
            fails.append("the cached re-run disagrees with the mine")

        # -- 6. OFI arithmetic, by hand ------------------------------------
        print("\n  OFI by hand, so the sign convention is checked and not")
        print("  merely commented.")
        # A level that MOVES counts its whole new size as arrival and does
        # NOT net off the level it left -- the old level is gone, not sold.
        # A bid stepping up is buying pressure of the entire new level; an
        # ask stepping down is selling pressure of the entire new level.
        cases = [
            ((40, 100, 42, 100), (40, 150, 42, 100), +50, "size added at bid"),
            ((40, 100, 42, 100), (40, 100, 42, 150), -50, "size added at ask"),
            ((40, 100, 42, 100), (40, 60, 42, 100), -40, "bid size pulled"),
            ((40, 100, 42, 100), (41, 80, 42, 100), +80, "bid steps up"),
            ((40, 100, 42, 100), (39, 70, 42, 100), -100, "bid steps down"),
            ((40, 100, 42, 100), (40, 100, 41, 90), -90, "ask steps down"),
            ((40, 100, 42, 100), (40, 100, 43, 70), +100, "ask steps up"),
            ((40, 100, 42, 100), None, None, "book goes invalid"),
        ]
        for old, new, want, what in cases:
            got = ofi_step(old, new)
            ok = (got is None) if want is None else (
                got is not None and abs(got - want) < 1e-9)
            gs = "    None" if got is None else f"{got:+8.1f}"
            ws = "    None" if want is None else f"{want:+8.1f}"
            print(f"    {what:<22} {gs}  want {ws}  "
                  f"{'ok' if ok else 'WRONG'}")
            if not ok:
                fails.append(f"OFI sign wrong for '{what}': {got} vs {want}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fails:
        print("=" * 78)
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        print("=" * 78)
        return False
    print("=" * 78)
    print("SELF-TEST PASSED -- finds a planted effect, reads zero on a real")
    print("flow at the wrong moment and on a market that cannot be predicted,")
    print("catches a dropped message, and emits the quiet seconds too.")
    print("=" * 78)
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--cache", default="./flow_cache")
    ap.add_argument("--tau", type=int, default=TAU_MAX)
    ap.add_argument("--max-msgs", type=int, default=None)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    from replay import load_markets
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    markets = load_markets(a.out)
    if not markets:
        print(f"\n  *** NO SETTLED MARKETS at {os.path.abspath(a.out)}.")
        return
    if not os.path.isdir(os.path.join(a.data, "orderbook_delta")):
        print("\n  no orderbook_delta on disk -- nothing to analyse")
        return

    paths = mine(a.data, markets, a.cache, verbose=True, rebuild=a.rebuild,
                 max_msgs=a.max_msgs, tau=a.tau)
    book_summary(paths, verbose=True)
    rows = load_rows(paths, markets, verbose=True)
    if not rows:
        print("\n  no quotes -- nothing to analyse")
        return

    print("\n" + "=" * 78)
    print("DOES ORDER FLOW PREDICT THE NEXT MOVE?")
    print("=" * 78)
    print("  x = order flow imbalance over second t, in contracts")
    print("  y = mid change from the end of t to the end of t+k, in cents")
    print("  The MDE is printed with every line: a slope inside it is a")
    print("  measurement that could not have found anything, not a zero.")
    print()
    print("    horizon                                slope       t"
          "        MDE")
    for k in (1, 2, 5, 10, 30, 60):
        r = ols_cluster(pairs(rows, markets, k=k))
        show(f"k = {k:>3}s", r)

    print("\n  PLACEBO -- the same flow against a moment 300s away in the")
    print("  same market. Real x, wrong y. This must read zero.")
    for k in (1, 5, 30):
        show(f"k = {k:>3}s, shifted", ols_cluster(pairs(rows, markets, k=k,
                                                       shift=300)))

    print("\n  BACKWARD -- the move that has already finished. This must be")
    print("  strongly POSITIVE. If it is not, the wiring is wrong and the")
    print("  forward zeros above mean nothing.")
    for k in (1, 5, 30):
        show(f"k = {k:>3}s, backward", ols_cluster(pairs(rows, markets, k=k,
                                                        backward=True)))

    print("\n" + "=" * 78)
    print("MONEY -- slope fitted on the first half of the tape, traded on")
    print("the second, paying the real spread and the real fee both ways")
    print("=" * 78)
    for k in (1, 5, 10, 30):
        r = trade_oos(pairs(rows, markets, k=k), k)
        if r is None:
            print(f"    k = {k:>3}s   not enough data")
        elif r.get("mean") is None:
            print(f"    k = {k:>3}s   trained slope {r['b_train']:+.4f}c, "
                  f"only {r['trades']} trades cleared the cost of crossing")
        elif "t" not in r:
            print(f"    k = {k:>3}s   {r['trades']:,} trades, "
                  f"P&L {r['mean']:+.2f}c, too few closes to score")
        else:
            flag = "" if abs(r["mean"]) > r["mde"] else "   INSIDE THE MDE"
            print(f"    k = {k:>3}s   {r['trades']:,} trades over {r['G']} "
                  f"closes, P&L {r['mean']:+.2f}c  t={r['t']:+.2f}  "
                  f"MDE {r['mde']:.2f}c{flag}")

    print("\n  A slope that beats its MDE is a fact about the book. It is")
    print("  only money if the MONEY block above beats its own MDE too.")


if __name__ == "__main__":
    main()
