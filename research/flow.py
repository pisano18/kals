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

The output is one row per (market, second) -- not per message -- so 470
million messages become a few million rows, written once, cached per day, and
re-analysed in seconds.

ALL FOUR CHANNELS, NOT TWO

The collector subscribes to orderbook_delta, trade and ticker in ONE
`subscribe` call, so Kalshi numbers all three under one sid with one counter.
Reading `seq` off the orderbook messages alone reads every ticker and every
trade in between as a hole -- and a hole invalidates every book under the sid,
which here is every market at once. The first two runs did exactly that: ~460
"gaps" a day, 55 of 62 million deltas dropped onto invalid books, and 3% of
the tape surviving.

`ticker` earns its place twice. It carries the sequence numbers, and it
carries yes_bid, yes_ask and both sizes on every message -- so after a
GENUINE gap it re-anchors top of book in seconds rather than leaving the
market dark until the next snapshot, of which there are ~800 a day. Rows say
which source they came from; depth beyond the touch is only knowable from the
rebuilt book, so it is absent on a ticker-channel row rather than counted as
zero.

That also buys a cross-check nothing else in this project has: two
independent views of the same top of book, one replayed from 400 million
deltas and one handed over whole. The mine reports how often they agree.

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
from doctor import get_path, walk_paths, find_field         # noqa: E402
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
        if not isinstance(m, dict):
            # A truncated write can leave a line that is still VALID json --
            # `123` parses to an int, not a dict. json.JSONDecodeError does not
            # fire and `.get` raises three hundred million messages later. The
            # first real run died here, on the ninth of nine days.
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
        if not isinstance(m, dict):
            continue
        rx = m.get("_rx_ms")
        if isinstance(rx, (int, float)):
            return rx / 1000.0
        return _ts((m.get("msg") or {}).get("ts"))
    return None


CHANNELS = ("orderbook_snapshot", "orderbook_delta", "ticker", "trade")


def ob_files(data_dir):
    """EVERY channel in the subscription, grouped by the UTC day of its first
    message.

    Not just the two orderbook ones, and the difference is the whole run. The
    collector subscribes to orderbook_delta, trade and ticker in ONE
    `subscribe` call, so Kalshi numbers all three under one sid with one
    counter. Reading seq off the orderbook messages alone means every ticker
    and every trade in between reads as a hole -- and a hole invalidates every
    book under the sid, which here is every market at once. The first run
    logged ~460 "gaps" a day and dropped 55 of 62 million deltas onto invalid
    books.

    `ticker` earns its place twice over: it carries yes_bid, yes_ask AND both
    sizes on every message, so after a genuine gap it re-anchors top of book
    in seconds instead of waiting for the next snapshot -- of which there are
    only ~800 a day. `trade` is read for its sequence numbers alone.

    Grouped by day so the mine can cache and resume. A day boundary costs the
    first few seconds of book validity on each market alive across it, until
    Kalshi's next snapshot -- against re-reading 3.6 GB to add one day, which
    is the difference between a stage that can be re-run and one that cannot.
    """
    files = []
    for ch in CHANNELS:
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
def _resolve_ticker(sample):
    """Field paths and price unit for the `ticker` channel, read off the data.

    Discovered, never assumed: Kalshi renamed these once already and
    68,976,084 of 68,976,084 deltas went unparsed while every stage exited 0.
    """
    paths = defaultdict(lambda: defaultdict(int))
    for m in sample:
        walk_paths(m, out=paths)
    f = {c: find_field(paths, c) for c in
         ("ticker", "yes_bid", "yes_ask", "bid_size", "ask_size")}
    mx = 0.0
    for m in sample:
        for c in ("yes_bid", "yes_ask"):
            if f.get(c):
                try:
                    mx = max(mx, abs(float(get_path(m, f[c]))))
                except (TypeError, ValueError):
                    pass
    f["scale"] = 100.0 if mx <= 1.5 else 1.0
    return f


def mine_day(files, windows, verbose=False, max_msgs=None):
    """One day of every channel -> rows, in bounded memory.

    `windows` is ticker -> (start_sec, end_sec): the only seconds worth
    emitting. Everything else is applied to the book and dropped, so the
    output is proportional to the markets we can actually score rather than
    to the tape.

    A row is:
        (ticker, sec, bid_c, ask_c, bid_sz, ask_sz, ofi, nmsg, dbid, dask, src)
    with prices in integer cents, the book state as of the END of `sec`, and
    `ofi` accumulated over the messages that arrived DURING `sec`. `src` says
    which channel the top of book came from: B for the reconstructed delta
    book, T for the ticker channel after a gap. Depth beyond the touch is
    only knowable from the book, so it is zero on a T row.
    """
    stats = defaultdict(int)
    gap_sizes = []
    rows = []
    if not files:
        return rows, stats

    ob_sample, tk_sample = [], []
    for fp in files:
        want_tk = os.sep + "ticker" + os.sep in fp
        if (want_tk and len(tk_sample) >= 1500) or \
           (not want_tk and len(ob_sample) >= 2000):
            continue
        for line in salvage_lines(fp):
            try:
                mm = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(mm, dict):
                continue
            (tk_sample if want_tk else ob_sample).append(mm)
            if len(tk_sample) >= 1500 and len(ob_sample) >= 2000:
                break
            if (want_tk and len(tk_sample) >= 1500) or \
               (not want_tk and len(ob_sample) >= 2000):
                break
    scale = _resolve_ob(ob_sample)["scale"]
    TF = _resolve_ticker(tk_sample)
    stats["scale"] = scale
    # Printed, not assumed. Kalshi renamed these once and 68,976,084 of
    # 68,976,084 deltas went unparsed while every stage exited 0; if the
    # sizes stop resolving, ticker-channel rows quietly lose their order
    # flow and nothing else says so.
    stats["ticker_fields"] = str({k: v for k, v in TF.items() if v})

    books = defaultdict(Book)
    sid_tk = defaultdict(set)      # subscription -> the tickers under it
    sid_seq = {}
    tl1 = {}                       # ticker -> L1 from the `ticker` channel
    last_l1 = {}                   # ticker -> (l1, src) after the last message
    cur = {}                       # ticker -> (sec being accumulated, ofi, n)
    live = {}                      # ticker -> (start, end) for tickers in play
    gclock = 0

    def state_of(tk):
        """Top of book now, and where it came from.

        The reconstructed book wins when it is valid -- it is the higher
        resolution source and the only one that knows depth. When a genuine
        sequence gap has invalidated it, the ticker channel still carries
        yes_bid, yes_ask and both sizes, so the market stays measurable
        instead of going dark until the next snapshot.
        """
        bk = books.get(tk)
        if bk is not None and bk.valid:
            l1 = _l1(bk)
            if l1 is not None:
                db, da = bk.depth_within(3)
                return l1, "B", (db or 0.0), (da or 0.0)
        t = tl1.get(tk)
        if t is not None:
            return t, "T", 0.0, 0.0
        return None

    def emit(tk, sec, ofi, n):
        st = state_of(tk)
        if st is None:
            stats["sec_invalid"] += 1
            return
        (b, bs, a, as_), src, db, da = st
        stats["rows_" + src] += 1
        rows.append((tk, sec, b, a, bs, as_, ofi, n, db, da, src))

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
            tl1.pop(tk, None)
            last_l1.pop(tk, None)
        else:
            cur[tk] = (max(s, upto), 0.0, 0)

    def sweep(now):
        """Carry every live market forward to the global clock."""
        for tk in list(cur):
            flush(tk, now)

    def account(tk, sec, w):
        """Fold this message into the second it belongs to, with its flow."""
        st_now = state_of(tk)
        new = (st_now[0], st_now[1]) if st_now else None
        old = last_l1.get(tk)
        # A CHANGE OF SOURCE IS NOT ORDER FLOW. Switching between the
        # reconstructed book and the ticker channel moves the numbers for
        # reasons that have nothing to do with anyone trading, and the jump
        # would be booked as an enormous imbalance.
        if old is not None and new is not None and old[1] != new[1]:
            e = None
            stats["ofi_reset_source_change"] += 1
        else:
            e = ofi_step(old[0] if old else None, new[0] if new else None)
        last_l1[tk] = new

        if tk not in live:
            live[tk] = w
        cs = cur.get(tk)
        if cs is None:
            cur[tk] = (sec, e or 0.0, 1)
        elif cs[0] >= sec:
            # `>=`, not `==`. Replaying in seq order means a message can carry
            # a receive stamp a second EARLIER than the one being accumulated.
            # Starting a new second for it would discard the flow already
            # gathered for the later one; folding it in is right at
            # one-second resolution, and the reordering spans milliseconds.
            cur[tk] = (cs[0], cs[1] + (e or 0.0), cs[2] + 1)
        else:
            flush(tk, sec)
            cur[tk] = (sec, e or 0.0, 1)

    # ------------------------------------------------------------------
    # THE REORDER BUFFER
    #
    # `_rx_ms` is a MILLISECOND local receive stamp, and the merge breaks ties
    # by file. Two messages that share a millisecond but sit in different
    # channel directories are therefore delivered in alphabetical order of
    # channel, not in the order Kalshi sent them. On the 2026-09-03 run that
    # showed up as 74-198 "restarts" and 426-712 "gaps" a day with a MEDIAN
    # GAP SIZE OF 1 -- the signature of a single adjacent pair swapped, which
    # reads as one step backwards and then one step forwards.
    #
    # It is not cosmetic. `Book.apply` deletes a level whose size reaches
    # zero, so a subtraction applied before its matching addition destroys the
    # level permanently. That is why the replayed book agreed with the ticker
    # channel on only 81% of comparisons, and why 92% of rows had to fall back
    # to the ticker channel.
    #
    # seq is the true order, so messages are held until they can be applied in
    # seq order. The buffer is bounded: once PENDING_MAX messages are waiting
    # on one that never comes, that one really is missing and the gap is
    # declared. A gap of 65,840,809 therefore costs 4,096 buffered messages,
    # not 65 million.
    PENDING_MAX = 4096
    pend = defaultdict(dict)
    expect = {}

    def handle(t, m, typ, d, tk, is_snap, is_delta, is_tick, seq, sid):
        nonlocal gclock
        w = windows.get(tk)
        if w is None:
            stats["no_settlement"] += 1
            return
        sec = int(t)
        if sec > gclock:
            gclock = sec
            sweep(gclock)
        if sec > w[1]:
            return                    # past this market's window entirely
        sid_tk[sid].add(tk)

        if is_tick:
            b = _cents(get_path(m, TF["yes_bid"]) if TF.get("yes_bid")
                       else d.get("yes_bid"), TF["scale"])
            a_ = _cents(get_path(m, TF["yes_ask"]) if TF.get("yes_ask")
                        else d.get("yes_ask"), TF["scale"])
            try:
                bs = float(get_path(m, TF["bid_size"]) if TF.get("bid_size")
                           else d.get("yes_bid_size") or 0.0)
                as_ = float(get_path(m, TF["ask_size"]) if TF.get("ask_size")
                            else d.get("yes_ask_size") or 0.0)
            except (TypeError, ValueError):
                bs = as_ = 0.0
            if b is None or a_ is None or not (0 < b < a_ < 100):
                stats["ticker_unusable"] += 1
                return
            stats["ticker_msgs"] += 1
            tl1[tk] = (b, bs, a_, as_)
            # AGREEMENT, ON REAL DATA. Where the reconstructed book is valid
            # and the ticker channel has just spoken, the two independent
            # views of top-of-book must match. This is the only check in the
            # project that scores the delta replay against something it did
            # not itself produce.
            bk = books.get(tk)
            if bk is not None and bk.valid:
                bl = _l1(bk)
                if bl is not None:
                    stats["agree_n"] += 1
                    if bl[0] == b and bl[2] == a_:
                        stats["agree_exact"] += 1
                    elif abs(bl[0] - b) <= 1 and abs(bl[2] - a_) <= 1:
                        stats["agree_1c"] += 1
            if sec >= w[0]:
                account(tk, sec, w)
            return

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
                return
            if not bk.valid:
                stats["delta_while_invalid"] += 1
                return
            bk.apply(price, chg, side, t)
            stats["deltas"] += 1

        if sec < w[0]:
            return                    # before the window: book state only
        account(tk, sec, w)

    def parse(m):
        typ = m.get("type", "")
        d = m.get("msg") or {}
        is_snap = "orderbook_snapshot" in typ
        is_delta = "orderbook_delta" in typ
        is_tick = typ == "ticker"
        if not (is_snap or is_delta or is_tick or typ == "trade"):
            return None
        tk = (get_path(m, TF["ticker"]) if is_tick and TF.get("ticker")
              else None) or d.get("market_ticker") or d.get("ticker")
        if not tk:
            stats["no_ticker"] += 1
            return None
        return typ, d, tk, is_snap, is_delta, is_tick

    def dispatch(t, m, P, seq, sid):
        typ, d, tk, is_snap, is_delta, is_tick = P
        if typ == "trade":
            stats["trades_seen"] += 1
            return
        handle(t, m, typ, d, tk, is_snap, is_delta, is_tick, seq, sid)

    def invalidate(sid):
        for other in sid_tk[sid]:
            b2 = books.get(other)
            if b2 is not None and b2.valid:
                b2.valid = False
                stats["books_invalidated"] += 1

    def drain(sid):
        dq = pend[sid]
        while dq:
            e = expect[sid]
            got = dq.pop(e, None)
            if got is None:
                return
            dispatch(got[0], got[1], got[2], e, sid)
            expect[sid] = e + 1

    streams = [_file_stream(fp, i) for i, fp in enumerate(files)]
    n_read = 0
    for t, _fi, _li, m in merge(*streams):
        n_read += 1
        if max_msgs and n_read > max_msgs:
            break
        P = parse(m)
        if P is None:
            continue
        sid = m.get("sid")
        sid = P[2] if sid is None else sid
        seq = m.get("seq")
        if not isinstance(seq, int):
            sq = P[1].get("seq")
            seq = sq if isinstance(sq, int) else None
        if seq is None:
            dispatch(t, m, P, None, sid)  # no sequence to order by
            continue

        e = expect.get(sid)
        if e is None:
            stats["sids"] += 1
            expect[sid] = seq + 1
            dispatch(t, m, P, seq, sid)
        elif seq == e:
            expect[sid] = seq + 1
            dispatch(t, m, P, seq, sid)
            if pend[sid]:
                drain(sid)
        elif seq > e:
            pend[sid][seq] = (t, m, P)
            if len(pend[sid]) > PENDING_MAX:
                # PENDING_MAX messages have arrived and the one we are
                # waiting for is not among them. It is genuinely lost, and
                # every book under this subscription is fiction until a
                # snapshot -- or until the ticker channel re-anchors it.
                nxt = min(pend[sid])
                stats["seq_gaps"] += 1
                gap_sizes.append(nxt - e)
                invalidate(sid)
                expect[sid] = nxt
                drain(sid)
        else:
            # seq below what we expect. Inside the buffer's reach that is a
            # late arrival we have already given up on; far below it, the
            # subscription's counter restarted -- the collector re-subscribes
            # every thirty seconds and a reconnect renumbers from 1.
            if e - seq > PENDING_MAX:
                stats["seq_restarts"] += 1
                pend[sid].clear()
                expect[sid] = seq + 1
                dispatch(t, m, P, seq, sid)
            else:
                stats["late_arrival"] += 1
                dispatch(t, m, P, seq, sid)

    # whatever is still buffered is in order among itself
    for sid in list(pend):
        for sq in sorted(pend[sid]):
            got = pend[sid][sq]
            dispatch(got[0], got[1], got[2], sq, sid)
        pend[sid].clear()

    sweep(gclock + 1)
    for tk in list(cur):
        flush(tk, gclock + 1)
    stats["rows"] = len(rows)
    stats["messages"] = n_read
    stats["markets_emitted"] = len({r[0] for r in rows})
    if gap_sizes:
        gap_sizes.sort()
        stats["gap_size_median"] = gap_sizes[len(gap_sizes) // 2]
        stats["gap_size_max"] = gap_sizes[-1]
        stats["gap_under_100"] = sum(1 for g in gap_sizes if g < 100)
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


# Bumped whenever the mine's OUTPUT would change for the same input. The
# per-day cache is what makes this stage re-runnable, and it is also what
# would have silently served eight days of the sequence-restart bug back after
# the fix was pushed. The version is in the FILENAME, so a stale file is
# ignored rather than overwritten -- and can still be read by hand.
CACHE_VERSION = 4
CACHE_HDR = ("ticker,sec,bid_c,ask_c,bid_sz,ask_sz,ofi,nmsg,dbid,dask,src\n")


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
        fp = os.path.join(cache_dir, f"{day}.v{CACHE_VERSION}.csv.gz")
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
                f.write("%s,%d,%d,%d,%.2f,%.2f,%.4f,%d,%.2f,%.2f,%s\n"
                        % r)
        os.replace(tmp, fp)
        paths.append(fp)
        if verbose:
            print(f"    {day}: {st['rows']:,} rows over "
                  f"{st['markets_emitted']:,} markets, from "
                  f"{st['messages']:,} messages")
            print(f"        ticker fields {st['ticker_fields']}")
            print(f"        deltas applied {st['deltas']:,}  "
                  f"snapshots {st['snapshots']:,}  "
                  f"subscriptions {st['sids']:,}  "
                  f"unparsed {st['unparsed_delta']:,}")
            # WHERE THE DATA WENT. The first run printed rows and gaps and
            # nothing else, and "105,876 rows" looked like a small tape rather
            # than a 99% loss. Every line below is a place market-seconds go
            # to die, so a repeat of that failure names itself.
            print(f"        seq restarts {st['seq_restarts']:,}  "
                  f"REAL gaps {st['seq_gaps']:,} "
                  f"(median {st['gap_size_median']:,}, "
                  f"max {st['gap_size_max']:,} msgs, "
                  f"{st['gap_under_100']:,} under 100)")
            print(f"        books invalidated {st['books_invalidated']:,}  "
                  f"deltas dropped on an invalid book "
                  f"{st['delta_while_invalid']:,}  "
                  f"seconds with no top of book at all "
                  f"{st['sec_invalid']:,}")
            print(f"        rows from the rebuilt book {st['rows_B']:,}  "
                  f"from the ticker channel after a gap {st['rows_T']:,}  "
                  f"ticker msgs {st['ticker_msgs']:,}  "
                  f"trades {st['trades_seen']:,}")
            # THE CROSS-CHECK. Two independent views of top of book, one
            # replayed from 400 million deltas and one handed to us whole.
            # If they disagree, the replay is wrong and every number above
            # it is decoration.
            if st["agree_n"]:
                ex = 100.0 * st["agree_exact"] / st["agree_n"]
                w1 = 100.0 * (st["agree_exact"] + st["agree_1c"]) / st["agree_n"]
                print(f"        rebuilt book vs ticker channel: "
                      f"{ex:.1f}% exact, {w1:.1f}% within 1c, "
                      f"on {st['agree_n']:,} comparisons")
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
                if len(p) != 11:
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
                if len(p) != 11:
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
                # Depth beyond the touch is only knowable from the rebuilt
                # book. A ticker-channel row has no view past level one, and
                # averaging its zero into the quartiles would halve the very
                # number the maker verdict rests on.
                if p[10].strip() == "B":
                    near.append((db + da) / 2.0)
    if not n:
        return None
    spreads.sort(); touch.sort(); near.sort()
    if not near:
        near = [0.0]

    def q(v, f):
        return v[min(len(v) - 1, int(f * len(v)))]
    r = {"n": n,
         "spread": (q(spreads, .25), q(spreads, .5), q(spreads, .75)),
         "touch": (q(touch, .25), q(touch, .5), q(touch, .75)),
         "near3": (q(near, .25), q(near, .5), q(near, .75)),
         "near_n": len(near)}
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
              f"{r['near3'][2]:>8.0f}   (rebuilt-book rows only, "
              f"{r['near_n']:,})")
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
def _write_feed(root, spec, seed=7, predictive=True, drop_seq=False,
                restart_seq=False, jitter=False):
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
    dirs = {ch: os.path.join(root, ch) for ch in CHANNELS}
    for v in dirs.values():
        os.makedirs(v, exist_ok=True)
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
                # The real collector subscribes orderbook_delta, trade and
                # ticker in ONE call, so all three share a sid and a single
                # seq counter. A fixture carrying only the orderbook channels
                # cannot show that reading seq off one channel reads the
                # other two as holes -- the bug that dropped 55 of 62 million
                # deltas onto invalid books.
                msgs.append({"type": "ticker", "sid": 1, "seq": nxt(),
                             "_rx_ms": t1 + 4,
                             "msg": {"market_ticker": tk,
                                     "yes_bid": bid / 100.0,
                                     "yes_ask": ask / 100.0,
                                     "yes_bid_size": float(yes.get(bid, 0.0)),
                                     "yes_ask_size": float(
                                         no.get(100 - ask, 0.0))}})
                msgs.append({"type": "trade", "sid": 1, "seq": nxt(),
                             "_rx_ms": t1 + 5,
                             "msg": {"market_ticker": tk, "count": 1}})
            pend = 0

            msgs.append({"type": "ticker", "sid": 1, "seq": nxt(),
                         "_rx_ms": int(sec * 1000) + 195,
                         "msg": {"market_ticker": tk,
                                 "yes_bid": bid / 100.0,
                                 "yes_ask": ask / 100.0,
                                 "yes_bid_size": float(yes.get(bid, 0.0)),
                                 "yes_ask_size": float(no.get(100 - ask,
                                                              0.0))}})
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
    if jitter:
        # WHAT THE REAL TAPE LOOKS LIKE. `_rx_ms` is a millisecond stamp and
        # the merge breaks ties by channel directory, so messages that share
        # a millisecond arrive in alphabetical order of channel rather than
        # the order Kalshi sent them. Coarsening the clock AFTER seq is
        # assigned reproduces exactly that: seq still carries the truth, the
        # arrival order no longer does.
        # 100ms, and the grid was MEASURED not chosen: at 10ms this fixture
        # produces 0 out-of-seq arrivals in 36,628 messages and the test is
        # vacuous. At 100ms it produces 8,211. A test that cannot fail is
        # worse than no test, because it reads as coverage.
        for m in msgs:
            m["_rx_ms"] = (m["_rx_ms"] // 100) * 100
    if drop_seq:
        dd = [i for i, m in enumerate(msgs) if "delta" in m["type"]]
        del msgs[dd[len(dd) // 2]]
    if restart_seq:
        # What the collector actually does: it re-subscribes every 30 seconds
        # for newly opened windows, and on reconnect the sid numbering starts
        # over, so an old sid's counter reappears at 1 under a number already
        # seen. Nothing is missing -- the stream simply began again.
        h = len(msgs) // 2
        for j, m in enumerate(msgs[h:], start=1):
            m["seq"] = j

    for ch, dv in dirs.items():
        part = [m for m in msgs if m["type"] == ch]
        with gzip.open(os.path.join(dv, "a.jsonl.gz"), "wt",
                       encoding="utf-8") as f:
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
              f"unparsed {h['unparsed_delta']}, "
              f"ticker msgs {h['ticker_msgs']:,}, trades {h['trades_seen']:,}")
        if h["seq_gaps"] or h["delta_while_invalid"] or h["unparsed_delta"]:
            fails.append("an intact feed produced gaps or unparsed deltas -- "
                         "the reader is inventing holes, and on real data "
                         "that silently discards the channel")
        if not h["ticker_msgs"] or not h["trades_seen"]:
            fails.append("the ticker and trade channels were not read. They "
                         "share the subscription's seq counter, so ignoring "
                         "them reads every one of them as a hole.")
        if h["rows_T"]:
            fails.append(f"{h['rows_T']} rows fell back to the ticker channel "
                         "on a feed with no gaps -- the rebuilt book should "
                         "be authoritative throughout")
        # THE CROSS-CHECK, on the fixture, where the answer is known exactly.
        ex = 100.0 * h["agree_exact"] / max(1, h["agree_n"])
        print(f"    rebuilt book vs ticker channel: {ex:.1f}% exact on "
              f"{h['agree_n']:,} comparisons")
        if h["agree_n"] < 100 or ex < 99.9:
            fails.append(f"the replayed book and the ticker channel agree on "
                         f"only {ex:.1f}% of {h['agree_n']:,} comparisons -- "
                         "two views of the same top of book must match")

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

        # -- 4b. a seq RESTART is not a gap --------------------------------
        print("\n  The sequence RESTARTS mid-stream, the way it does every")
        print("  time the collector re-subscribes. Nothing is missing, so")
        print("  nothing may be invalidated.")
        d4 = os.path.join(tmp, "restart")
        mk4 = _write_feed(d4, _spec(20, 2, seed=13), seed=13,
                          restart_seq=True)
        r4, s4 = mine_day(sorted(glob.glob(os.path.join(d4, "*", "*.gz"))),
                          windows_from_markets(mk4), verbose=False)
        d5 = os.path.join(tmp, "clean")
        mk5 = _write_feed(d5, _spec(20, 2, seed=13), seed=13)
        r5, s5 = mine_day(sorted(glob.glob(os.path.join(d5, "*", "*.gz"))),
                          windows_from_markets(mk5), verbose=False)
        print(f"    restarts seen {s4['seq_restarts']:,}, real gaps "
              f"{s4['seq_gaps']:,}, books invalidated "
              f"{s4['books_invalidated']:,}")
        print(f"    rows {len(r4):,} vs {len(r5):,} on the same feed without "
              "the restart")
        if s4["seq_restarts"] == 0:
            fails.append("the fixture restarted the sequence and the reader "
                         "did not notice -- this test proves nothing")
        if s4["books_invalidated"] or s4["seq_gaps"]:
            fails.append(f"a sequence RESTART was counted as "
                         f"{s4['seq_gaps']} gaps and invalidated "
                         f"{s4['books_invalidated']} books. This is the bug "
                         "that cost the first real run 99% of its rows.")
        if len(r4) != len(r5):
            fails.append(f"the restart changed the output: {len(r4):,} rows "
                         f"vs {len(r5):,}. A renumbered stream carries the "
                         "same book.")

        # -- 4c. a gap must cost seconds, not the rest of the day ----------
        print("\n  A real gap invalidates the book -- correctly. But the")
        print("  ticker channel still carries top of book, so the market")
        print("  must stay measurable instead of going dark until the next")
        print("  snapshot, of which there are ~800 a day against ~460 gaps.")
        d6 = os.path.join(tmp, "recover")
        mk6 = _write_feed(d6, _spec(8, 2, seed=9), seed=9, drop_seq=True)
        r6, s6 = mine_day(sorted(glob.glob(os.path.join(d6, "*", "*.gz"))),
                          windows_from_markets(mk6), verbose=False)
        print(f"    gaps {s6['seq_gaps']}, books invalidated "
              f"{s6['books_invalidated']}, rows kept {len(r6):,} "
              f"({s6['rows_B']:,} from the book, {s6['rows_T']:,} from the "
              f"ticker channel), seconds lost {s6['sec_invalid']:,}")
        if s6["seq_gaps"] == 0 or s6["books_invalidated"] == 0:
            fails.append("the gap fixture produced no gap -- this test "
                         "proves nothing")
        if s6["rows_T"] == 0:
            fails.append("a gap took the market dark. The ticker channel is "
                         "on disk and carries top of book; not using it is "
                         "how 55 of 62 million deltas landed on invalid "
                         "books.")
        if s6["sec_invalid"]:
            fails.append(f"{s6['sec_invalid']:,} seconds had no top of book "
                         "at all despite the ticker channel being available")

        # -- 4d. same messages, millisecond ties, wrong arrival order ------
        print("\n  The same feed with a coarser receive clock, so messages")
        print("  sharing a millisecond arrive in channel order rather than")
        print("  the order they were sent. seq still carries the truth. The")
        print("  output must be IDENTICAL to the cleanly ordered feed.")
        d7 = os.path.join(tmp, "clean2")
        mk7 = _write_feed(d7, _spec(20, 2, seed=21), seed=21)
        r7, s7 = mine_day(sorted(glob.glob(os.path.join(d7, "*", "*.gz"))),
                          windows_from_markets(mk7), verbose=False)
        d8 = os.path.join(tmp, "jitter")
        mk8 = _write_feed(d8, _spec(20, 2, seed=21), seed=21, jitter=True)
        r8, s8 = mine_day(sorted(glob.glob(os.path.join(d8, "*", "*.gz"))),
                          windows_from_markets(mk8), verbose=False)
        print(f"    ordered: {len(r7):,} rows, gaps {s7['seq_gaps']}, "
              f"restarts {s7['seq_restarts']}, from the ticker channel "
              f"{s7['rows_T']:,}")
        print(f"    jittered: {len(r8):,} rows, gaps {s8['seq_gaps']}, "
              f"restarts {s8['seq_restarts']}, from the ticker channel "
              f"{s8['rows_T']:,}, late arrivals {s8['late_arrival']:,}")
        if s8["seq_gaps"] or s8["seq_restarts"]:
            fails.append(f"a millisecond tie produced {s8['seq_gaps']} gaps "
                         f"and {s8['seq_restarts']} restarts. Nothing is "
                         "missing -- the messages merely arrived out of "
                         "order, and calling that a gap invalidates every "
                         "book under the subscription.")
        if s8["rows_T"]:
            fails.append(f"{s8['rows_T']:,} rows fell back to the ticker "
                         "channel on a feed with nothing missing")
        if len(r8) != len(r7) or r8 != r7:
            fails.append("reordering the arrivals changed the output. seq is "
                         "the true order and replaying in it must be "
                         "deterministic.")

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
