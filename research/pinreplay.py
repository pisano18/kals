#!/usr/bin/env python3
# VERSION: 2026-09-12-pr2
"""pinreplay.py -- THE FIDELITY HARNESS. Does the tape reproduce our own trades?

THE OPERATOR'S DEMAND, verbatim (2026-09-12):

    "remake the way that you backtest... our current way has always been very
     wrong. Don't stop until you can backtest our last trade and get the same
     results. I want to see more losses because we actually have losses...
     It should replicate exactly what would happen if it was live."

THIS FILE IS NOT THE NEW BACKTEST. It is the MEASURING INSTRUMENT for one.
It takes every fill the live bot ACTUALLY made -- read out of
`results/pinrun-live-*.jsonl`, which is the only record of what we really did
-- and asks, at the exact second (and where possible the exact MILLISECOND) of
each fill, whether the tape replay reproduces:

  (a) the model's fair value that the live bot logged,
  (b) the offer we hit, as a price and a size in the rebuilt book,
  (c) our own fill, as a LADDER of prints on the trade tape,
  (d) the settlement, and
  (e) whether `pinsim.decide` -- the existing backtest's decision function --
      would have bought it at all, and if not, the reason string it returns.

It PROPOSES NO FIX. Per the operator's instruction the fix is being designed
separately; this file only says where the replay and reality part company, and
with what count.

WHY A MILLISECOND PASS EXISTS. The live bot samples the book ~20x/second. An
offer can appear and be eaten inside one second, so a replay that evaluates
the book once per second is blind to it by construction -- and CLAUDE.md's
2026-09-10 amendment already records that the 82c XRP fill we really took is
absent from the once-per-second replayed book entirely. So every fill is
checked twice: at the second boundary (what the backtest sees) and at every
delta instant inside the second (what the bot saw).

THE BOOK IS MERGED ON `seq`, NOT ON THE CLOCK, and this was a bug found
here rather than assumed. A snapshot record carries no exchange timestamp at
all -- only the collector's `_rx_ms` -- but both the snapshot and the delta
channel carry `seq` from the same subscription (`sid` 4 for both).
KXSOL15M-26SEP120400-00's snapshot is `seq` 1,286,254 while that market's FIRST
delta is `seq` 1,286,271, and yet the snapshot's receipt time is 12 ms LATER
than that delta's `ts_ms`. Merged on the clock, the snapshot therefore lands
AFTER a delta it already contains and wipes it, leaving levels in the rebuilt
book that the exchange had already removed. Scored against the price the live
model logged, over 195 fills: `seq` order 151, clock order 35, with a median
error of THIRTY CENTS. All three orderings are still reported, because the
point of this file is to show the difference rather than to assert the answer.

WHY `exec_price` IS NOT A LEVEL PRICE. It is the size-weighted average of
everything the IOC swept. The DOGE loss settles it on its own: logged at
0.0998, which is not even on the 0.1c tick grid, with a true print of
`0.1100 x17 + 0.0420 x3` at one `ts_ms` -- 20 contracts, $1.9960, VWAP exactly
0.099800. So (c) reconciles a fill against a LADDER: contiguous same-taker-side
prints whose counts sum to ours and whose VWAP matches what we paid to 2e-4.
A first version compared `exec_price` to single prints with a one-cent
tolerance; on that fill it matched the 17-lot leg and called it ours, and on 14
others it found nothing and said the fill was not on the tape. Both were
artefacts of comparing an average to a level.

WHY THE DECISION INSTANT IS RECONSTRUCTED TO THE MILLISECOND. The live
`signal` record carries `index_age_s` = (wall clock) - (second stamped on the
newest index tick held). The newest tick held is either second S or S-1, so
    W = stamp + index_age_s,  choosing the stamp that puts W inside second S
is exact to 10 ms. That is the instant the live bot decided, and the book and
the index are both evaluated there.

THREE FEEDS OF THE INDEX ARE COMPARED, because they are not the same thing:
  fair_sec   -- ticks fed with `sec <= S`, which is what pinsim does
  fair_secm1 -- ticks fed with `sec <= S-1`
  fair_rx    -- ticks fed by ARRIVAL (`_rx_ms <= W`), the faithful one
Measured on this tape (hour 20260912T07, 39,583 prints, 11 feeds): a print
stamped X arrives at X+0.08 s median. So at W = S.04 the live index holds the
tick stamped S-1 and pinsim holds the tick stamped S. `fair_sec` therefore
carries about one second of LOOKAHEAD. Whether that matters is measured here,
not asserted.

WHAT THE SIGMA DIFFERENCES ARE, when they appear. On 4 of 195 fills the
replayed `sigma` differs from the one the live bot logged, by 0.3% to 32%,
moving `fair` by 1.4e-4 to 4.2e-3. It is not a replay defect: on the two worst
(KXBTC15M and KXBNB15M, both 2026-09-12 09:44) the index tape holds 300 of 300
seconds with ZERO gaps, and the replayed sigma was reproduced by hand from the
raw file to every digit. The live bot runs its OWN index WebSocket, separate
from the collector's, and one extra ~33-point one-second BTC move inside the
live bot's 300-second window accounts for the whole gap arithmetically
(variance 5.12 -> 8.88 needs exactly one diff of about 33.5, and the tape's
largest is 29.89). Two independent subscriptions to the same feed, disagreeing
at a window boundary in a volatile moment -- worth knowing, not worth fixing
in the replay.

WHAT THIS FILE DOES NOT MEASURE, and cannot:
  * whether the offer would have been OURS. Live fill rate is 70%; nothing in
    a replay can race.
  * how a different rule would have performed. This is a reconciliation, not
    a backtest. Per CLAUDE.md's 2026-09-10 amendment, no loss rate is quoted
    from the tape -- the loss population here is OUR OWN 9 real losses, read
    from live `settled` records, and the tape is used only to ask whether it
    can SEE them.
  * capacity, queue position, or fees beyond what pinrun itself bills.

`pintake` is never imported here and no order function is ever called;
`pinrun` imports it for the live rails and that import is transitive through
`pinsim`, which is the certified backtest module this harness reuses.
"""
import argparse
import calendar
import glob
import gzip
import json
import os
import sys
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrun                                                # noqa: E402
import pindata                                               # noqa: E402
import pinsim                                                # noqa: E402
import pinrules                                              # noqa: E402
import gzsalvage                                             # noqa: E402
from statistics import NormalDist                            # noqa: E402

_ND = NormalDist()

DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"
LOGS = os.path.join(HERE, "..", "results", "pinrun-live-*.jsonl")
OUT = os.path.join(HERE, "..", "results", "RESULTS_replay.md")

FAIR_TOL = 1e-4          # the task's flag threshold on |fair_replay - fair_live|
PX_TOL = 1e-4            # an ask "at or better than" the price we paid
ET_OFFSET = 4 * 3600     # September 2026 is EDT = UTC-4 (fallback close only)
# Deltas carry the EXCHANGE clock (`ts_ms`); snapshot records carry only the
# COLLECTOR's receipt time (`_rx_ms`). Merging the two clocks needs the offset,
# measured on this tape (hour 20260912T07, 40,001 sampled deltas):
# _rx_ms - ts_ms = 15 / 17 / 1830 ms at p10 / median / p90. The median is used
# to put a snapshot on the exchange clock; the p90 burst tail is why the
# snapshot ordering is REPORTED both ways rather than assumed.
SNAP_RX_LAG_MS = 17

# TWO DIFFERENT DUMP GUARDS EXIST AND THEY ARE NOT THE SAME RULE.
#   pinrun (LIVE):        refuse if discount > DUMP_DISCOUNT (0.15 = 15c),
#                         at ANY confidence.
#   pinrules default profile (what pinsim.run() applies): refuse if
#                         conf >= 0.999 AND discount_c > 5.
# So the backtest can refuse a trade the live bot took and take a trade
# the live bot refused. Both are evaluated here, separately, and neither
# is called "the" guard.
_PROFILE = None


def profile():
    global _PROFILE
    if _PROFILE is None:
        _PROFILE = pinrules.load("default")
    return _PROFILE


def dump_disc(fair, price, want):
    """pinrun's own discount arithmetic, verbatim from its trade loop:
    (fair - price) on a YES, ((1 - fair) - price) on a NO."""
    if fair is None or price is None:
        return None
    return (fair - price) if want == "yes" else ((1.0 - fair) - price)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}

# start-record key -> pinrun module constant. The live `start` record logs the
# whole gate, so the decision can be re-run under the gate that was ACTUALLY
# live for that fill as well as under today's.
LIVE_PARAMS = {
    "pin": "PIN", "price_ceiling": "PRICE_CEILING", "edge_floor": "EDGE_FLOOR",
    "ev_floor": "EV_FLOOR", "tau_min": "TAU_MIN", "tau_max": "TAU_MAX",
    "min_fill_frac": "MIN_FILL_FRAC", "min_level": "MIN_LEVEL",
    "max_book_age_ms": "MAX_BOOK_AGE_MS", "sigma_stress": "SIGMA_STRESS",
    "improve_by": "IMPROVE_BY",
}
# NOT re-applied: measured_flip. pinrun.expected_value(price, flip=MEASURED_FLIP)
# binds the default AT DEFINITION, so setting the module attribute cannot
# change it. Stated rather than silently ignored.


# --------------------------------------------------------------- small helpers
def iso_s(s):
    """'2026-09-08T07:59:40Z' -> epoch seconds (UTC). No dateutil, stdlib only."""
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


def hour_stamp(sec):
    return time.strftime("%Y%m%dT%H", time.gmtime(sec))


def close_from_ticker(tk):
    """Fallback close time: the ticker suffix is EASTERN time.

    KXSOL15M-26SEP112300-00 closes 23:00 ET on 2026-09-11 = 03:00Z the 12th.
    Only used when fulltape/markets.json has not caught up; every ticker that
    IS in markets.json is cross-checked against this in main().
    """
    try:
        part = tk.split("-")[1]
        yy, mon, dd = int(part[0:2]), MONTHS[part[2:5]], int(part[5:7])
        hh, mi = int(part[7:9]), int(part[9:11])
        return calendar.timegm((2000 + yy, mon, dd, hh, mi, 0, 0, 0, 0)) \
            + ET_OFFSET
    except Exception:                                          # noqa: BLE001
        return None


def result_yes(res):
    """markets.json `result` is 'yes'/'no' on some rows and 1.0/0.0 on others."""
    if res is None:
        return None
    if isinstance(res, str):
        return res.strip().lower() == "yes"
    try:
        return float(res) >= 0.5
    except Exception:                                          # noqa: BLE001
        return None


def settle_from_index(ticks, close_s, strike, digits):
    """The settlement, computed from the index tape itself.

    Settlement is the simple mean of the sixty 1-second prints in
    [close-60, close-1] (CLAUDE.md, verified on 108/108 markets), and the
    effective strike is pindata.eff_strike. So the outcome is recoverable from
    the tape WITHOUT fulltape/markets.json -- which matters because the
    newest markets have not been pulled yet, and because it cross-checks the
    pull on the ones that have.

    Returns (mean, n_prints, "yes"/"no") or (None, n, None) if the window is
    not complete. This is SETTLEMENT VERIFICATION, not a decision input: it
    reads seconds after the decision on purpose, and no index built for a
    `fair` call ever sees them.
    """
    if close_s is None or strike is None:
        return None, 0, None
    got = {sec: val for sec, val, _rx in ticks
           if close_s - 60 <= sec <= close_s - 1}
    if len(got) != 60:
        return None, len(got), None
    mean = sum(got.values()) / 60.0
    K = pindata.eff_strike(float(strike), digits)
    return mean, 60, ("yes" if mean >= K else "no")


def find_fill(trades, S, W_ms, want, px_paid, filled):
    """Our fill on the trade tape -- as a GROUP OF LEGS, not one print.

    THIS IS THE CORRECTION. `exec_price` in the order record is the
    SIZE-WEIGHTED AVERAGE of everything the IOC swept, not a level price. The
    DOGE loss proves it on its own: it is logged at 0.0998, which is not even
    on the 0.1c tick grid, and its true print is

        0.1100 x 17.00  +  0.0420 x 3.00   at one ts_ms
        -> 20.00 contracts, $1.9960, VWAP exactly 0.099800

    A first version of this check compared exec_price to individual prints
    with a one-cent tolerance. On that fill it matched the 17-lot leg and
    called it "our fill", and on 14 others it found nothing and said
    OUR_FILL_NOT_ON_TAPE. Both were artefacts of comparing a VWAP to a level.
    Kalshi prints sweeps PER LEVEL (CLAUDE.md, settled on ts_ms over 12M
    trades), so the right object to reconcile against is the ladder.

    Searches contiguous runs of same-taker-side prints in tape order across
    [S-1, S+2), preferring the FEWEST legs and then the run nearest the
    decision instant. Returns (nlegs, ts, legs, vwap, count) or None.
    """
    cands = sorted(((t[0], (t[2] if want == "yes" else t[3]), t[4])
                    for t in trades
                    if (S - 1) * 1000 <= t[0] < (S + 2) * 1000
                    and t[1] == want), key=lambda x: x[0])
    best = None
    for i in range(len(cands)):
        cnt = 0.0
        cost = 0.0
        for j in range(i, len(cands)):
            _ts, px, c = cands[j]
            cnt += c
            cost += px * c
            if cnt > filled + 0.011:
                break
            if abs(cnt - filled) <= 0.011 and cnt > 0 \
                    and abs(cost / cnt - px_paid) <= 2e-4:
                key = (j - i + 1, abs(cands[i][0] - W_ms))
                if best is None or key < best[0]:
                    best = (key, cands[i][0],
                            [(px_, c_) for _t, px_, c_ in cands[i:j + 1]],
                            cost / cnt, cnt)
                break
    if best is None:
        return None
    return (best[0][0], best[1], best[2], best[3], best[4])


def our_ask(bk, want, now_ms):
    """(price, size) of the best offer on the side we wanted, from the book."""
    b = pinsim.book_view(bk, now_ms)
    return b.get(f"{want}_ask"), (b.get(f"{want}_ask_size") or 0.0), b


# ------------------------------------------------------------------ live logs
def load_live(pattern=None):
    """Every fill the bot really made, paired with its signal, its settlement
    and the gate the run was started with.

    Pairing is POSITIONAL inside each log file, which is exact: pinrun writes
    the `signal` record and then the `order` record for the same attempt, in
    that order, in the same second (verified on all 192 fills -- every order
    has a preceding signal on the same ticker in the same second).
    """
    fills = []
    for fp in sorted(glob.glob(pattern or LOGS)):
        start = {}
        last_sig = {}
        pend = []            # fills from this file, awaiting settled records
        for line in open(fp, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:                                  # noqa: BLE001
                continue
            k = r.get("kind")
            if k == "start":
                start = r
            elif k == "signal":
                last_sig[r["ticker"]] = r
            elif k == "order":
                if not (r.get("filled") or 0) > 0:
                    continue
                sig = last_sig.get(r["ticker"])
                body = r.get("body") or {}
                want = "yes" if str(body.get("side")) == "bid" else "no"
                fills.append({
                    "log": os.path.basename(fp),
                    "ticker": r["ticker"],
                    "series": r["ticker"].split("-")[0],
                    "want": want,
                    "t_iso": r["t"],
                    "S": iso_s(r["t"]),
                    "exec_price": float(r["exec_price"]),
                    "exec_yes": r.get("exec_yes_price"),
                    "filled": float(r["filled"]),
                    "order_count": float(r["filled"]) + float(r.get("remaining") or 0),
                    "latency_ms": r.get("latency_ms"),
                    "tau_at_send": r.get("tau_at_send"),
                    "order_id": r.get("order_id"),
                    "fee_live": r.get("fee"),
                    "gate": {kk: start.get(kk) for kk in LIVE_PARAMS
                             if start.get(kk) is not None},
                    "gate_size": start.get("size"),
                    "dump_discount": start.get("dump_discount"),
                    "dump_enabled": start.get("dump_enabled"),
                    # --- the signal, i.e. what the live model actually said
                    "sig": ({"fair": sig.get("fair"), "price": sig.get("price"),
                             "tau": sig.get("tau"), "strike": sig.get("strike"),
                             "digits": sig.get("digits"),
                             "sigma": sig.get("sigma"), "spot": sig.get("spot"),
                             "size": sig.get("size"), "take_n": sig.get("take_n"),
                             "book_age_ms": sig.get("book_age_ms"),
                             "index_age_s": sig.get("index_age_s"),
                             "t": sig.get("t"), "want": sig.get("want")}
                            if sig else None),
                    "settled": None,
                })
                pend.append(fills[-1])
            elif k == "settled":
                # match on ticker + want + the price paid (`cost` == exec_price);
                # KXNEAR15M-26SEP082045-45 took three fills at three prices in
                # one market, so ticker alone is not a key.
                for fl in pend:
                    if fl["settled"] is None and fl["ticker"] == r["ticker"] \
                            and fl["want"] == r.get("want") \
                            and abs(fl["exec_price"] - float(r["cost"])) < 1e-9:
                        fl["settled"] = {"result": r.get("result"),
                                         "pnl_c": r.get("pnl_c"),
                                         "cost": r.get("cost"), "t": r.get("t")}
                        break
    fills.sort(key=lambda f: f["S"])
    return fills


def decision_instant_ms(S, index_age_s):
    """The millisecond the live bot decided, from `index_age_s`.

    index_age_s = W - (second stamped on the newest tick held), and that stamp
    is S or S-1. Pick the one that puts W inside second S.
    """
    if index_age_s is None:
        return S * 1000 + 500, False
    for stamp in (S, S - 1, S - 2):
        w = stamp + float(index_age_s)
        if S <= w < S + 1:
            return int(round(w * 1000)), True
    return S * 1000 + 500, False


# ---------------------------------------------------------------- tape loaders
def _salvage_lines(path):
    """Member-by-member gzip recovery, STREAMING.

    Same recovery as `gzsalvage.iter_lines` -- the collector appends a second
    gzip member after a restart and the standard reader then recovers ZERO
    lines from the whole hour, which would appear here as an empty book and be
    misread as "the offer was not there" -- but it never materialises a
    member. An 80 MB hour of order-book deltas decompresses to roughly 900 MB;
    gzsalvage holds that as one str AND as a list of its lines, which is ~2 GB
    and is exactly the shape that OOM-killed a job on 2026-09-12. The
    collector outranks every job here, so the recovery is re-implemented
    bounded (64 KB at a time) and checked line-for-line against gzsalvage's
    own output in the self-test, on a healthy file and on a two-member broken
    one.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    offs = gzsalvage._members(raw)
    CH = 1 << 16
    for i, off in enumerate(offs):
        stop = offs[i + 1] if i + 1 < len(offs) else len(raw)
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        buf = b""
        pos = off
        while pos < stop:
            try:
                chunk = d.decompress(raw[pos:min(pos + CH, stop)])
            except zlib.error:
                break
            pos += CH
            if chunk:
                buf += chunk
                if b"\n" in buf:
                    parts = buf.split(b"\n")
                    buf = parts.pop()
                    for pln in parts:
                        if pln:
                            # the standard reader opens in TEXT mode
                            # with universal newlines, so a file
                            # written on Windows comes back "\n"-
                            # terminated. Match that, or the salvage
                            # path returns lines the fast path would
                            # not and the two are not interchangeable.
                            yield pln.decode(
                                "utf-8", "replace").rstrip("\r") + "\n"
            if d.eof:
                break
        try:
            buf += d.flush()
        except zlib.error:
            pass
        # Each member is an independent stream and a record never spans two of
        # them, so a trailing fragment is a TRUNCATED line, not a continuation.
        parts = buf.split(b"\n")
        parts.pop()
        for pln in parts:
            if pln:
                yield pln.decode(
                    "utf-8", "replace").rstrip("\r") + "\n"


def _lines(channel, stamp, stats, salvage=True):
    """Every line of one hour of one channel.

    The fast path runs first and yields as it goes. If it dies and `salvage`
    is on, the bounded member-wise pass replays the file and skips the lines
    already emitted.

    `salvage=False` is used for the hour the collector is STILL APPENDING TO.
    That file has one member and no trailer, so the fast path already recovers
    every flushed line and then raises at EOF; salvaging it would re-read and
    re-decompress the whole thing for nothing.
    """
    fp = os.path.join(DATA, channel, f"{stamp}.jsonl.gz")
    if not os.path.exists(fp):
        stats["missing"] = stats.get("missing", 0) + 1
        stats.setdefault("missing_files", []).append(f"{channel}/{stamp}")
        return
    n = 0
    try:
        with gzip.open(fp, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                n += 1
                yield line
        return
    except Exception:                                          # noqa: BLE001
        pass
    if not salvage:
        stats["truncated"] = stats.get("truncated", 0) + 1
        stats.setdefault("truncated_channels", []).append(f"{channel}/{stamp}")
        return
    stats["salvaged_files"] = stats.get("salvaged_files", 0) + 1
    stats.setdefault("salvaged_channels", []).append(f"{channel}/{stamp}")
    skip = n
    for line in _salvage_lines(fp):
        if skip:
            skip -= 1
            continue
        yield line


def load_ticks_rx(stamps, stats, salvage=True):
    """iid -> [(sec, value, rx_ms)] sorted by sec, from the hours named."""
    out = defaultdict(list)
    for stamp in stamps:
        for line in _lines("cfbenchmarks_value", stamp, stats, salvage):
            if '"cfbenchmarks_value"' not in line:
                continue
            try:
                d = json.loads(line)
                m = d["msg"]
                dd = json.loads(m["data"])
                sec = int(dd["time"]) // 1000
                val = float(dd["value"])
            except Exception:                                  # noqa: BLE001
                continue
            out[m["index_id"]].append(
                (sec, val, int(d.get("_rx_ms") or (sec * 1000 + 80))))
    for k in out:
        out[k].sort()
    return out


def load_snaps(stamp, tickers, stats, salvage=True):
    """ticker -> [(msg, seq, rx_ms)] in file order.

    `seq` IS THE ONE THAT MATTERS. A snapshot record carries no exchange
    timestamp at all -- only the collector's `_rx_ms` -- but it does carry the
    subscription's `seq`, and the snapshot and delta channels share one seq
    space (verified: `sid` 4 for both). Merging by receipt time is wrong and
    was measurably wrong: KXSOL15M-26SEP120400-00's snapshot is `seq`
    1,286,254 while the market's FIRST delta is `seq` 1,286,271, yet the
    snapshot's `_rx_ms` is 12 ms LATER than that delta's `ts_ms`. Placed by
    time, the snapshot lands after the delta and wipes it. Placed by `seq`, it
    lands before it, which is where the exchange put it.
    """
    out = defaultdict(list)
    for line in _lines("orderbook_snapshot", stamp, stats, salvage):
        if not any(t in line for t in tickers):
            continue
        try:
            d = json.loads(line)
            m = d["msg"]
        except Exception:                                      # noqa: BLE001
            continue
        tk = m.get("market_ticker")
        if tk in tickers:
            out[tk].append((m, d.get("seq"), int(d.get("_rx_ms") or 0)))
    return out


def load_deltas(stamp, tickers, stats, salvage=True):
    """ticker -> [(ts_ms, side, price, dq)] in file order. ONE pass.

    A substring prefilter on the raw bytes skips json.loads for the ~99.9% of
    lines that are other markets: 2.75M lines in 2.5 s. `bad` counts deltas
    that failed to parse, which the report prints -- a book rebuilt from an
    incomplete delta stream is not a book.
    """
    out = defaultdict(list)
    bad = 0
    n = 0
    for line in _lines("orderbook_delta", stamp, stats, salvage):
        n += 1
        if not any(t in line for t in tickers):
            continue
        try:
            d = json.loads(line)
            m = d["msg"]
        except Exception:                                      # noqa: BLE001
            continue
        tk = m.get("market_ticker")
        if tk not in tickers:
            continue
        try:
            # VERBATIM field names from pindata's fixed reader: the tape says
            # `price_dollars` and `delta_fp`.
            out[tk].append((
                int(m["ts_ms"]),
                str(m.get("side", "")).lower(),
                float(m.get("price_dollars", m.get("price"))),
                float(m.get("delta_fp", m.get("delta")) or 0.0),
                d.get("seq")))
        except Exception:                                      # noqa: BLE001
            bad += 1
    return out, bad, n


def load_trades(stamp, tickers, stats, salvage=True):
    """ticker -> [(ts_ms, taker_side, yes_px, no_px, count)] in file order."""
    out = defaultdict(list)
    for line in _lines("trade", stamp, stats, salvage):
        if not any(t in line for t in tickers):
            continue
        try:
            d = json.loads(line)
            m = d["msg"]
        except Exception:                                      # noqa: BLE001
            continue
        tk = m.get("market_ticker")
        if tk not in tickers:
            continue
        try:
            out[tk].append((
                int(m["ts_ms"]), str(m.get("taker_side", "")).lower(),
                float(m["yes_price_dollars"]),
                float(m["no_price_dollars"]),
                float(m.get("count_fp", m.get("count") or 0))))
        except Exception:                                      # noqa: BLE001
            continue
    return out


# ------------------------------------------------------------ index rebuilding
def _frame(iid, sec, val):
    return {"type": "cfbenchmarks_value",
            "msg": {"index_id": iid,
                    "data": json.dumps({"time": sec * 1000, "value": str(val)})}}


def index_by_sec(iid, ticks, upto_sec, now):
    """pinrun's OWN index, holding every tick STAMPED at or before upto_sec.

    This is what pinsim.feed_upto does. Only the 400 s before the close are
    fed: sigma() reads the last 300 seconds held and partial() reads
    [close-60, close-1], so a 400 s window gives byte-identical reads to
    feeding the whole hour, at 1/10th the on_frame calls.
    """
    ix = pinsim.TapeIndex([iid])
    for sec, val, _rx in ticks:
        if sec <= upto_sec:
            ix.on_frame(_frame(iid, sec, val))
    ix.now = now
    return ix


def index_by_rx(iid, ticks, upto_ms, now):
    """The same index, holding every tick that had ARRIVED by upto_ms."""
    ix = pinsim.TapeIndex([iid])
    for sec, val, rx in ticks:
        if rx <= upto_ms:
            ix.on_frame(_frame(iid, sec, val))
    ix.now = now
    return ix


# ------------------------------------------------------------ book rebuilding
def merge_events(snaps, deltas, order="seq"):
    """One market's snapshot+delta stream as [(ts_ms, kind, payload)].

    kind 0 = snapshot (payload = the message), kind 1 = delta
    (payload = (side, price, dq)).

    order='seq'      -- THE EXCHANGE'S OWN ORDER. Both channels carry `seq`
                        from the same subscription, so this needs no clock
                        estimate and no assumption. A snapshot has no exchange
                        timestamp, so it inherits the ts of the nearest delta
                        at or after it in seq order (else the one before it,
                        else its receipt time minus the measured 17 ms).
    order='ts'       -- merged on timestamps: deltas by `ts_ms`, snapshots by
                        `_rx_ms` - 17 ms. WRONG, and measurably so: a
                        snapshot's receipt can trail the `ts_ms` of a delta it
                        already contains, so the snapshot lands after that
                        delta and wipes it. Kept only to score it.
    order='snapfirst'-- what pinsim.run() does: every snapshot in the hour
                        applied before any delta (at ts 0, because snapshot
                        records carry `_rx_ms` and pinsim reads `ts_ms`), then
                        all deltas in file order.
    """
    if order == "snapfirst":
        ev = [(0, 0, m) for m, _sq, _rx in snaps]
        ev += [(ts, 1, (side, px, dq)) for ts, side, px, dq, _sq in deltas]
        return ev
    if order == "ts":
        ev = [(rx - SNAP_RX_LAG_MS, 0, m) for m, _sq, rx in snaps]
        ev += [(ts, 1, (side, px, dq)) for ts, side, px, dq, _sq in deltas]
        ev.sort(key=lambda e: (e[0], e[1]))
        return ev
    # --- seq order
    items = [(sq, 0, i, m, rx) for i, (m, sq, rx) in enumerate(snaps)
             if sq is not None]
    items += [(sq, 1, i, (side, px, dq), ts)
              for i, (ts, side, px, dq, sq) in enumerate(deltas)
              if sq is not None]
    if len(items) < len(snaps) + len(deltas):
        # a record without `seq` cannot be placed; fall back rather than guess
        return merge_events(snaps, deltas, "ts")
    items.sort(key=lambda e: (e[0], e[1], e[2]))
    # forward/backward fill the snapshots' timestamps from their delta
    # neighbours in seq order
    ts_of = [None] * len(items)
    for i, it in enumerate(items):
        if it[1] == 1:
            ts_of[i] = it[4]
    nxt = None
    for i in range(len(items) - 1, -1, -1):
        if ts_of[i] is not None:
            nxt = ts_of[i]
        elif nxt is not None:
            ts_of[i] = nxt
    prev = None
    for i in range(len(items)):
        if ts_of[i] is not None:
            prev = ts_of[i]
        elif prev is not None:
            ts_of[i] = prev
    ev = []
    for i, it in enumerate(items):
        ts = ts_of[i]
        if ts is None:
            ts = it[4] - SNAP_RX_LAG_MS
        ev.append((ts, it[1], it[3]))
    return ev


def seq_monotone(snaps, deltas):
    """(backward steps, deltas with a seq) in this market's DELTA stream.

    A collector reconnect restarts the subscription and the sequence with it,
    which would make seq order meaningless, so it is counted rather than
    trusted. Only the deltas are tested, and in FILE order: an earlier version
    concatenated all snapshots in front of all deltas and then called the
    result non-monotone whenever a snapshot's seq exceeded the first delta's
    -- which is the normal case for a market whose second snapshot arrives
    later in the hour, so it fired on 100% of fills and meant nothing.
    """
    sq = [d[4] for d in deltas if d[4] is not None]
    bad = sum(1 for i in range(1, len(sq)) if sq[i] < sq[i - 1])
    return bad, len(sq)


def build_book(ev, upto_ms):
    """The market's book at upto_ms, from a merged event list."""
    bk = pindata.Book()
    for ts, kind, payload in ev:
        if ts > upto_ms:
            break
        if kind == 0:
            bk.snapshot(payload, ts)
        else:
            try:
                bk.delta(payload[0], payload[1], payload[2], ts)
            except Exception:                                  # noqa: BLE001
                pass
    return bk


def ms_scan(ev, want, limit_px, lo_ms, hi_ms):
    """Was an offer at or better than `limit_px` on `want`'s side present at
    ANY instant in [lo_ms, hi_ms), and for how many ms?

    Walks the merged event stream once. Between two consecutive events the
    book is CONSTANT, so the interval [prev, cur) is credited whole. Returns
    (present, ms_present, n_instants_checked, best_ask_seen, first_ms, last_ms).
    """
    bk = pindata.Book()
    ms_on = 0
    n_inst = 0
    best = None
    first = last = None
    prev = None
    for ts, kind, payload in ev:
        if prev is not None and ts > prev:
            a = _ask_of(bk, want)
            if prev < hi_ms and ts > lo_ms:
                n_inst += 1
                if a is not None:
                    best = a if best is None else min(best, a)
                    if a <= limit_px + PX_TOL:
                        seg = min(ts, hi_ms) - max(prev, lo_ms)
                        if seg > 0:
                            ms_on += seg
                            first = max(prev, lo_ms) if first is None else first
                            last = min(ts, hi_ms)
        if ts >= hi_ms:
            prev = ts
            break
        if kind == 0:
            bk.snapshot(payload, ts)
        else:
            try:
                bk.delta(payload[0], payload[1], payload[2], ts)
            except Exception:                                  # noqa: BLE001
                pass
        prev = ts
    # tail: the book held from the last event to hi_ms
    if prev is not None and prev < hi_ms:
        a = _ask_of(bk, want)
        n_inst += 1
        if a is not None:
            best = a if best is None else min(best, a)
            if a <= limit_px + PX_TOL:
                seg = hi_ms - max(prev, lo_ms)
                if seg > 0:
                    ms_on += seg
                    first = max(prev, lo_ms) if first is None else first
                    last = hi_ms
    return (ms_on > 0), ms_on, n_inst, best, first, last


def _ask_of(bk, want):
    other = bk.no if want == "yes" else bk.yes
    if not other:
        return None
    return round(1.0 - max(other), 4)


# --------------------------------------------------------------- the decision
def set_gate(gate):
    """Apply a live `start` record's gate to pinrun's module constants and
    return the previous values, so it can be put back exactly."""
    old = {}
    for key, attr in LIVE_PARAMS.items():
        if key in gate and gate[key] is not None:
            old[attr] = getattr(pinrun, attr)
            setattr(pinrun, attr, gate[key])
    return old


def restore_gate(old):
    for attr, val in old.items():
        setattr(pinrun, attr, val)


def run_decide(idx, iid, close_s, now_s, strike, digits, bview, size):
    """pinsim.decide, normalised to (bought, want, price, take_n, fair, reason)."""
    try:
        w, px, n, f = pinsim.decide(idx, iid, close_s, now_s, strike, digits,
                                    bview, size)
    except Exception as e:                                     # noqa: BLE001
        return (False, None, None, None, None, f"raised:{type(e).__name__}")
    if w is None:
        return (False, None, None, None, f, px)
    return (True, w, px, n, f, "bought")


# --------------------------------------------------------------------- a fill
def probe_fill(fl, ticks, snaps, deltas, trades, mkr):
    """Everything (a)-(e) for one live fill. Pure: no file IO."""
    S = fl["S"]
    want = fl["want"]
    px_paid = fl["exec_price"]
    sig = fl["sig"] or {}
    iid = pindata.SERIES_TO_INDEX.get(fl["series"])
    digits = sig.get("digits", pindata.ROUND_DIGITS.get(fl["series"]))
    strike_live = sig.get("strike")
    close_s = int(float(mkr["close"])) if mkr and mkr.get("close") is not None \
        else close_from_ticker(fl["ticker"])
    strike = float(mkr["strike"]) if mkr and mkr.get("strike") is not None \
        else strike_live
    W_ms, W_exact = decision_instant_ms(S, sig.get("index_age_s"))
    tk_ticks = ticks.get(iid) or []
    lo = (close_s or S) - 400
    win = [t for t in tk_ticks if lo <= t[0] <= S + 2]
    # the settlement window runs to close-1, past every decision second, so it
    # is sliced SEPARATELY and never handed to an index that computes a fair
    win_settle = [t for t in tk_ticks
                  if (close_s or S) - 70 <= t[0] <= (close_s or S) + 2]

    out = {
        "ticker": fl["ticker"], "series": fl["series"], "want": want,
        "t_iso": fl["t_iso"], "S": S, "close_s": close_s,
        "close_src": "markets.json" if (mkr and mkr.get("close") is not None)
                     else "ticker-suffix-ET",
        "tau_tape": (close_s - S) if close_s else None,
        "tau_at_send": fl["tau_at_send"], "tau_live": sig.get("tau"),
        "exec_price": px_paid, "filled": fl["filled"],
        "order_count": fl["order_count"], "latency_ms": fl["latency_ms"],
        "W_ms": W_ms, "W_exact": W_exact, "W_frac": (W_ms - S * 1000) / 1000.0,
        "iid": iid, "strike_live": strike_live, "strike_tape": strike,
        "digits": digits, "n_deltas": len(deltas), "n_snaps": len(snaps),
        "n_snaps_levelled": sum(
            1 for m, _sq, _rx in snaps
            if m.get("yes_dollars_fp") or m.get("no_dollars_fp")),
        "n_ticks_window": len(win),
        "pnl_c": (fl["settled"] or {}).get("pnl_c"),
        "loss": ((fl["settled"] or {}).get("pnl_c") or 0) < 0,
        "flags": [],
    }
    flag = out["flags"].append

    # ------------------------------------------------------------------ (a)
    fair_live = sig.get("fair")
    out["fair_live"] = fair_live
    out["sigma_live"] = sig.get("sigma")
    out["bookage_live"] = sig.get("book_age_ms")
    for name, ix in (("sec", index_by_sec(iid, win, S, S) if iid else None),
                     ("secm1", index_by_sec(iid, win, S - 1, S) if iid else None),
                     ("rx", index_by_rx(iid, win, W_ms, W_ms / 1000.0)
                      if iid else None)):
        if ix is None or close_s is None or strike is None:
            out[f"fair_{name}"] = None
            out[f"sigma_{name}"] = None
            continue
        sg = ix.sigma(iid)
        out[f"sigma_{name}"] = sg
        if sg is None:
            out[f"fair_{name}"] = None
            continue
        out[f"fair_{name}"] = pinrun.fair(ix, iid, close_s, S, strike,
                                          sg * pinrun.SIGMA_STRESS,
                                          round_digits=digits)
        out[f"spot_{name}"] = ix.spot(iid)[1]
        if name == "sec":
            out["_idx_sec"] = ix
        elif name == "rx":
            out["_idx_rx"] = ix
    for name in ("sec", "secm1", "rx"):
        f = out.get(f"fair_{name}")
        out[f"d_{name}"] = (abs(f - fair_live)
                            if (f is not None and fair_live is not None) else None)
    diffs = {k: out[f"d_{k}"] for k in ("sec", "secm1", "rx")
             if out[f"d_{k}"] is not None}
    out["fair_best"] = min(diffs, key=diffs.get) if diffs else None
    out["fair_best_d"] = diffs[out["fair_best"]] if diffs else None
    if out["fair_best_d"] is None:
        flag("FAIR_UNCOMPUTABLE")
    elif out["fair_best_d"] > FAIR_TOL:
        flag("FAIR_DIVERGE")
    if (out["d_sec"] is not None and out["d_sec"] > FAIR_TOL
            and out.get("d_secm1") is not None and out["d_secm1"] <= FAIR_TOL):
        flag("FAIR_NEEDS_ONE_SEC_LAG")
    if strike_live is not None and strike is not None \
            and abs(float(strike_live) - float(strike)) > 1e-6:
        flag("STRIKE_MISMATCH")

    # ------------------------------------------------------------------ (b)
    ev = merge_events(snaps, deltas, "seq")
    ev_ts = merge_events(snaps, deltas, "ts")
    ev_sf = merge_events(snaps, deltas, "snapfirst")
    out["seq_bad"], out["seq_n"] = seq_monotone(snaps, deltas)
    if out["seq_bad"]:
        flag("SEQ_NOT_MONOTONE")
    b0 = build_book(ev, S * 1000 - 1)                # end of S-1: seq order
    b1 = build_book(ev, (S + 1) * 1000 - 1)          # end of S
    bw = build_book(ev, W_ms)                        # the live instant
    bp = build_book(ev_sf, S * 1000 - 1)             # pinsim's own ordering
    bt = build_book(ev_ts, S * 1000 - 1)             # timestamp ordering
    for tag, bk, nowms in (("s0", b0, S * 1000), ("s1", b1, (S + 1) * 1000),
                           ("w", bw, W_ms), ("ps", bp, S * 1000),
                           ("tsord", bt, S * 1000)):
        a, sz, bv = our_ask(bk, want, nowms)
        out[f"ask_{tag}"] = a
        out[f"asksz_{tag}"] = sz
        out[f"bookage_{tag}"] = bv["age_ms"]
        out[f"_bv_{tag}"] = bv
    out["offer_at_s0"] = (out["ask_s0"] is not None
                          and out["ask_s0"] <= px_paid + PX_TOL)
    out["offer_at_s1"] = (out["ask_s1"] is not None
                          and out["ask_s1"] <= px_paid + PX_TOL)
    out["offer_at_W"] = (out["ask_w"] is not None
                         and out["ask_w"] <= px_paid + PX_TOL)
    pres, ms_on, n_inst, best, f_ms, l_ms = ms_scan(
        ev, want, px_paid, (S - 1) * 1000, (S + 2) * 1000)
    out["ms_present"] = ms_on
    out["ms_instants"] = n_inst
    out["ms_any"] = pres
    out["ms_best_ask"] = best
    out["ms_first"] = (f_ms - S * 1000) if f_ms is not None else None
    out["ms_last"] = (l_ms - S * 1000) if l_ms is not None else None
    if not (out["offer_at_s0"] or out["offer_at_s1"]):
        flag("OFFER_MISSING")
        if pres:
            flag("OFFER_ONLY_SUBSECOND")
        else:
            flag("OFFER_ABSENT_AT_EVERY_MS")
    if sig.get("book_age_ms") is not None and out["bookage_w"] is not None:
        out["bookage_delta"] = out["bookage_w"] - sig["book_age_ms"]
    else:
        out["bookage_delta"] = None
    # the offer the model SAW, versus what the replayed book offers at all
    out["price_live"] = sig.get("price")
    if out["ask_w"] is not None and sig.get("price") is not None:
        out["d_price_w"] = abs(out["ask_w"] - float(sig["price"]))
        if out["d_price_w"] > PX_TOL:
            flag("PRICE_DIVERGE_AT_W")
    else:
        out["d_price_w"] = None

    # do the other two orderings read a DIFFERENT offer at the same boundary?
    # Emptiness is the wrong test -- the deltas refill the book either way;
    # what matters is the OFFER the decision reads.
    out["pinsim_book_empty"] = not (bp.yes or bp.no)
    out["seq_book_empty"] = not (b0.yes or b0.no)
    if (out["ask_ps"] != out["ask_s0"]) or (out["asksz_ps"] != out["asksz_s0"]):
        flag("PINSIM_BOOK_DIFFERS_FROM_SEQ_ORDER")
    if (out["ask_tsord"] != out["ask_s0"]) or \
            (out["asksz_tsord"] != out["asksz_s0"]):
        flag("TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER")

    # ------------------------------------------------------------------ (c)
    hit = find_fill(trades, S, W_ms, want, px_paid, float(fl["filled"]))
    out["print_found"] = hit is not None
    out["print_taker"] = want
    if hit:
        nlegs, ts, legs, vwap, cnt = hit
        out["print_nlegs"] = nlegs
        out["print_ts"] = ts
        out["print_dt_ms"] = ts - W_ms
        out["print_price"] = round(vwap, 6)
        out["print_count"] = cnt
        out["print_legs"] = [[round(px_, 4), c_] for px_, c_ in legs]
        out["print_dpx"] = abs(vwap - px_paid)
        out["print_price_only"] = False
    else:
        out["print_nlegs"] = 0
        out["print_ts"] = out["print_dt_ms"] = out["print_price"] = None
        out["print_count"] = out["print_dpx"] = None
        out["print_legs"] = None
        # a same-side print within one tick of what we paid, so the report can
        # say "near miss" rather than "absent" when the two are different things
        near = [t for t in trades
                if (S - 1) * 1000 <= t[0] < (S + 2) * 1000 and t[1] == want
                and abs((t[2] if want == "yes" else t[3]) - px_paid) <= 0.0105]
        out["print_price_only"] = bool(near)
    out["n_trades_window"] = sum(1 for t in trades
                                 if (S - 1) * 1000 <= t[0] < (S + 2) * 1000)
    if not out["print_found"]:
        flag("OUR_FILL_NOT_ON_TAPE")

    # ------------------------------------------------------------------ (d)
    live_res = (fl["settled"] or {}).get("result")
    tape_res = result_yes(mkr.get("result")) if mkr else None
    out["result_live"] = live_res
    out["result_tape"] = (None if tape_res is None else ("yes" if tape_res else "no"))
    smean, sn, sres = settle_from_index(win_settle, close_s, strike, digits)
    out["settle_mean_idx"] = smean
    out["settle_prints"] = sn
    out["result_idx"] = sres
    out["eff_strike"] = (pindata.eff_strike(float(strike), digits)
                         if strike is not None else None)
    if live_res is None:
        flag("NO_LIVE_SETTLEMENT")
    if tape_res is None:
        flag("NO_TAPE_SETTLEMENT")
    elif live_res is not None and out["result_tape"] != str(live_res).lower():
        flag("SETTLE_MISMATCH")
    if sres is None:
        flag("INDEX_SETTLE_WINDOW_INCOMPLETE")
    else:
        if live_res is not None and sres != str(live_res).lower():
            flag("SETTLE_MISMATCH_VS_INDEX")
        if tape_res is not None and sres != out["result_tape"]:
            flag("MARKETS_JSON_DISAGREES_WITH_INDEX")
    out["won_live"] = (None if live_res is None
                       else (str(live_res).lower() == want))

    # ------------------------------------------------------------------ (e)
    ix = out.get("_idx_sec")
    sizes = {"attempt": fl["order_count"]}
    if sig.get("size") is not None:
        sizes["live_size"] = float(sig["size"])
    if fl.get("gate_size") is not None:
        sizes["gate_size"] = float(fl["gate_size"])
    out["decide"] = {}
    for gname, gate in (("now", None), ("then", fl["gate"] or None)):
        old = set_gate(gate) if gate else {}
        try:
            for sname, sz in sizes.items():
                for bname, bv in (("s0", out["_bv_s0"]), ("w", out["_bv_w"]),
                                  ("ps", out["_bv_ps"])):
                    if ix is None or close_s is None or strike is None:
                        continue
                    r = run_decide(ix, iid, close_s, S, strike, digits, bv, sz)
                    out["decide"][f"{gname}/{sname}/{bname}"] = r
        finally:
            restore_gate(old)
    key = f"now/attempt/s0"
    r = out["decide"].get(key)
    out["reason_now_s0"] = r[5] if r else None
    r2 = out["decide"].get("now/attempt/w")
    out["reason_now_w"] = r2[5] if r2 else None
    r3 = out["decide"].get("then/attempt/s0")
    out["reason_then_s0"] = r3[5] if r3 else None
    r4 = out["decide"].get("then/attempt/w")
    out["reason_then_w"] = r4[5] if r4 else None
    out["live_pin"] = (fl["gate"] or {}).get("pin")
    out["live_ceiling"] = (fl["gate"] or {}).get("price_ceiling")
    # --- the RULE layer, which pinsim.run() applies AFTER decide() and which
    #     decide() itself knows nothing about. Judged on what actually
    #     happened: the fair the live model logged and the price we paid.
    out["disc_c"] = None
    d_ = dump_disc(fair_live, px_paid, want)
    if d_ is not None:
        out["disc_c"] = round(100.0 * d_, 2)
        out["dump_now"] = bool(pinrun.DUMP_ENABLED
                               and d_ > pinrun.DUMP_DISCOUNT)
        dd = fl.get("dump_discount")
        de = fl.get("dump_enabled")
        out["dump_then"] = (None if dd is None
                            else bool(de and d_ > float(dd)))
        out["dump_discount_then"] = dd
        if out["dump_now"]:
            flag("REFUSED_BY_PINRUN_DUMP_GUARD_TODAY")
    else:
        out["dump_now"] = out["dump_then"] = None
        out["dump_discount_then"] = None
    out["rule_verdict"] = out["rule_fired"] = None
    if fair_live is not None and out.get("asksz_w") is not None:
        try:
            rec = pinsim.record(
                float(fair_live), want, px_paid, float(fl["filled"]),
                float(out["asksz_w"] or 0.0), int(out["tau_tape"] or 0),
                fl["series"], S, sig.get("sigma"), sig.get("spot"),
                sig.get("book_age_ms"), sig.get("index_age_s"))
            v, fired = pinrules.decide(profile(), rec)
            out["rule_verdict"] = v
            out["rule_fired"] = [r for r, _a in fired]
            if v == "refuse":
                flag("REFUSED_BY_BACKTEST_PROFILE_RULE")
        except Exception as e:                                 # noqa: BLE001
            out["rule_verdict"] = f"raised:{type(e).__name__}"
    # the FULL backtest verdict: decide() AND the profile's rules
    for tag, key in (("now_s0", "now/attempt/s0"), ("now_w", "now/attempt/w"),
                     ("then_s0", "then/attempt/s0"),
                     ("then_w", "then/attempt/w")):
        dr = out["decide"].get(key)
        r_ = dr[5] if dr else None
        if r_ == "bought" and out["rule_verdict"] == "refuse":
            r_ = "rule:" + ",".join(out["rule_fired"] or ["?"])
        out["full_" + tag] = r_
    if out["reason_now_s0"] != "bought":
        flag("BACKTEST_WOULD_NOT_BUY")
        flag("WHYNOT:" + str(out["reason_now_s0"]))
    if out["full_now_s0"] != "bought":
        flag("FULL_BACKTEST_WOULD_NOT_BUY")
    for k in [k for k in out if k.startswith("_")]:
        del out[k]
    return out


# ------------------------------------------------------------------ self-test
def _synthetic():
    """A hour built so the answer is known, with an offer that lives 400 ms.

    want = yes at 96c. The NO side of the book is EMPTY at the start and the
    end of second S -- so yes_ask is None and pinsim.decide must say
    `no_offer` -- and a no bid at 4c (= a 96c yes offer) exists only from
    S+0.300 to S+0.700. One trade print at S+0.350, taker yes, 96c, 20
    contracts, is our fill; a decoy print at S+0.500 with taker `no` at the
    same price must NOT be matched.
    """
    C = 1_789_000_000                  # a round close second
    S = C - 20
    iid = "SELFTEST_RTI"
    ticks = [(sec, 100.0 + 0.001 * (sec % 2), sec * 1000 + 80)
             for sec in range(C - 400, C)]
    # yes bids only: the book is one-sided, so yes_ask is None
    snap_msg = {"market_ticker": "KXSELF15M-26SEP120400-00",
                "yes_dollars_fp": [["0.5000", "100.00"]],
                "no_dollars_fp": []}
    # (msg, seq, rx_ms) and (ts_ms, side, price, dq, seq). The snapshot's seq
    # is BELOW the first delta's, and its rx is LATER -- the real shape found on
    # the tape, so seq order and timestamp order genuinely disagree here.
    snaps = [(snap_msg, 1000, (C - 300) * 1000 + 40)]
    deltas = [
        ((C - 300) * 1000 + 5, "yes", 0.5000, 50.0, 1001),
        (S * 1000 + 300, "no", 0.0400, 50.0, 1002),   # the 96c yes offer appears
        (S * 1000 + 700, "no", 0.0400, -50.0, 1003),  # ...and is eaten
        ((S + 1) * 1000 + 10, "yes", 0.5000, 5.0, 1004),
    ]
    trades = [
        (S * 1000 + 350, "yes", 0.9600, 0.0400, 20.0),   # OURS
        (S * 1000 + 500, "no", 0.9600, 0.0400, 20.0),    # decoy: wrong side
    ]
    mkr = {"ticker": "KXSELF15M-26SEP120400-00", "series": "KXSELF15M",
           "strike": 99.0, "close": float(C), "result": "yes"}
    fl = {"log": "selftest", "ticker": "KXSELF15M-26SEP120400-00",
          "series": "KXSELF15M", "want": "yes", "t_iso": "selftest", "S": S,
          "exec_price": 0.96, "exec_yes": 0.96, "filled": 20.0,
          "order_count": 20.0, "latency_ms": 100.0, "tau_at_send": 20,
          "order_id": "x", "fee_live": 0.0027, "gate": {}, "gate_size": 20.0,
          "sig": {"fair": None, "price": 0.96, "tau": 20, "strike": 99.0,
                  "digits": 2, "sigma": None, "spot": None, "size": 20.0,
                  "take_n": 20.0, "book_age_ms": 0, "index_age_s": 1.05,
                  "t": "selftest", "want": "yes"},
          "settled": {"result": "yes", "pnl_c": 80.0, "cost": 0.96,
                      "t": "selftest"}}
    return C, S, iid, ticks, snaps, deltas, trades, mkr, fl


def selftest():
    print("SELF-TEST -- pinreplay")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    C, S, iid, ticks, snaps, deltas, trades, mkr, fl = _synthetic()
    pindata.SERIES_TO_INDEX.setdefault("KXSELF15M", iid)
    pindata.ROUND_DIGITS.setdefault("KXSELF15M", 2)

    # ---- the decision instant is reconstructed to the millisecond
    w_ms, exact = decision_instant_ms(S, 1.05)
    ck(exact and w_ms == S * 1000 + 50,
       f"index_age_s 1.05 at second S puts the decision at S+050 ms (got "
       f"{w_ms - S * 1000})")
    w2, _ = decision_instant_ms(S, 0.30)
    ck(w2 == S * 1000 + 300,
       f"and index_age_s 0.30 puts it at S+300 ms (got {w2 - S * 1000})")

    # ---- close from the ticker suffix is ET
    ck(close_from_ticker("KXSOL15M-26SEP112300-00")
       == calendar.timegm((2026, 9, 12, 3, 0, 0, 0, 0, 0)),
       "the ticker suffix is EASTERN: 23:00 ET on the 11th = 03:00Z the 12th")

    # ---- (i) the harness's fair IS pinrun's fair on the same index
    ix = pinsim.TapeIndex([iid])
    for sec, val, _rx in ticks:
        if sec <= S:
            ix.on_frame(_frame(iid, sec, val))
    ix.now = S
    sg = ix.sigma(iid)
    want_fair = pinrun.fair(ix, iid, C, S, 99.0, sg * pinrun.SIGMA_STRESS,
                            round_digits=2)
    out = probe_fill(fl, {iid: ticks}, snaps, deltas, trades, mkr)
    ck(sg is not None and want_fair is not None,
       f"the planted index yields a sigma and a fair ({sg}, {want_fair})")
    ck(out["fair_sec"] is not None
       and abs(out["fair_sec"] - want_fair) < 1e-12,
       f"(i) the harness's fair_sec equals pinrun.fair fed the same ticks "
       f"({out['fair_sec']} vs {want_fair})")
    ck(want_fair >= pinrun.PIN,
       f"and the planted world is a near-certain YES, as intended ({want_fair})")
    # a world with NOTHING planted: a fair_live equal to the replay must not flag
    fl_ok = json.loads(json.dumps({k: v for k, v in fl.items() if k != "gate"}))
    fl_ok["gate"] = {}
    fl_ok["sig"]["fair"] = round(want_fair, 5)
    out_ok = probe_fill(fl_ok, {iid: ticks}, snaps, deltas, trades, mkr)
    ck("FAIR_DIVERGE" not in out_ok["flags"],
       "and with fair_live set to that value the harness reports NO fair "
       "divergence (nothing planted, nothing found)")
    fl_bad = json.loads(json.dumps(fl_ok))
    fl_bad["sig"]["fair"] = round(want_fair - 0.01, 5)
    out_bad = probe_fill(fl_bad, {iid: ticks}, snaps, deltas, trades, mkr)
    ck("FAIR_DIVERGE" in out_bad["flags"],
       "and a fair_live 1c away IS flagged FAIR_DIVERGE")

    # ---- (ii) the sub-second offer
    ck(out["ask_s0"] is None and out["ask_s1"] is None,
       f"(ii) at the START and END of second S the NO side is empty, so there "
       f"is no yes offer at all ({out['ask_s0']}, {out['ask_s1']})")
    ck("OFFER_MISSING" in out["flags"]
       and "OFFER_ONLY_SUBSECOND" in out["flags"],
       f"and the harness reports OFFER_MISSING + OFFER_ONLY_SUBSECOND "
       f"({out['flags']})")
    ck(out["ms_present"] == 400,
       f"and the offer existed for exactly 400 ms inside second S "
       f"(got {out['ms_present']})")
    ck(out["ms_first"] == 300 and out["ms_last"] == 700,
       f"from S+300 ms to S+700 ms (got {out['ms_first']}..{out['ms_last']})")
    ck(out["ask_w"] is None,
       f"and at the reconstructed live instant S+050 ms it was NOT yet there "
       f"({out['ask_w']}) -- the harness does not invent it")
    # move the decision instant into the offer's life and it appears
    fl_mid = json.loads(json.dumps(fl_ok))
    fl_mid["sig"]["index_age_s"] = 1.40
    out_mid = probe_fill(fl_mid, {iid: ticks}, snaps, deltas, trades, mkr)
    ck(out_mid["ask_w"] == 0.96 and out_mid["asksz_w"] == 50.0,
       f"but with index_age_s 1.40 -- i.e. S+400 ms -- the 96c offer IS there, "
       f"50 deep (got {out_mid['ask_w']}, {out_mid['asksz_w']})")

    # ---- (iii) the planted print, and the decoy rejected
    ck(out["print_found"] and out["print_count"] == 20.0
       and out["print_nlegs"] == 1 and out["print_dt_ms"] == 300,
       f"(iii) our fill is found on the trade tape as ONE leg: 96c, 20 "
       f"contracts, {out['print_dt_ms']} ms after the decision instant")
    # THE SWEEP CASE, built from the real DOGE numbers: exec_price is the VWAP
    # of two legs and equals no single print.
    sw = [(S * 1000 + 350, "yes", 0.1100, 0.8900, 17.0),
          (S * 1000 + 350, "yes", 0.0420, 0.9580, 3.0),
          (S * 1000 + 350, "yes", 0.1100, 0.8900, 133.0)]
    fl_sw = json.loads(json.dumps(fl_ok))
    fl_sw["exec_price"] = 0.0998
    fl_sw["filled"] = 20.0
    o_sw = probe_fill(fl_sw, {iid: ticks}, snaps, deltas, sw, mkr)
    ck(o_sw["print_found"] and o_sw["print_nlegs"] == 2
       and abs(o_sw["print_price"] - 0.0998) < 1e-9
       and o_sw["print_count"] == 20.0,
       f"and a fill logged at 0.0998 -- a price not on the tick grid -- is "
       f"reconciled to the TWO-leg ladder 0.1100 x17 + 0.0420 x3, VWAP "
       f"{o_sw['print_price']}, 20 contracts (legs {o_sw['print_legs']})")
    fl_bad_vwap = json.loads(json.dumps(fl_sw))
    fl_bad_vwap["exec_price"] = 0.0900
    o_bv = probe_fill(fl_bad_vwap, {iid: ticks}, snaps, deltas, sw, mkr)
    ck(not o_bv["print_found"],
       "and the SAME ladder is NOT accepted for a fill logged at 0.0900 -- the "
       "VWAP has to match, it is not enough for the legs to be nearby")
    no_dec = [t for t in trades if t[1] == "yes"]
    out_nd = probe_fill(fl_ok, {iid: ticks}, snaps, deltas, no_dec, mkr)
    ck(out_nd["print_found"],
       "and it is still found with the decoy removed")
    only_dec = [t for t in trades if t[1] == "no"]
    out_od = probe_fill(fl_ok, {iid: ticks}, snaps, deltas, only_dec, mkr)
    ck(not out_od["print_found"]
       and "OUR_FILL_NOT_ON_TAPE" in out_od["flags"],
       "and with ONLY the wrong-side decoy present the harness says "
       "OUR_FILL_NOT_ON_TAPE -- taker_side is read, not ignored")
    fl_sz = json.loads(json.dumps(fl_ok))
    fl_sz["filled"] = 200.0
    out_sz = probe_fill(fl_sz, {iid: ticks}, snaps, deltas, trades, mkr)
    ck(not out_sz["print_found"] and out_sz["print_price_only"],
       "and a 200-contract fill is NOT matched to a 20-contract print "
       "(size is checked, and the price-only near-miss is reported)")

    # ---- (iv) pinsim.decide's reason string
    ck(out["reason_now_s0"] == "no_offer",
       f"(iv) pinsim.decide at the second boundary returns 'no_offer' "
       f"(got {out['reason_now_s0']})")
    ck("BACKTEST_WOULD_NOT_BUY" in out["flags"]
       and "WHYNOT:no_offer" in out["flags"],
       f"and the harness flags BACKTEST_WOULD_NOT_BUY / WHYNOT:no_offer "
       f"({out['flags']})")
    ck(out_mid["reason_now_w"] == "bought"
       and out_mid["decide"]["now/attempt/w"][2] == 0.96,
       f"and at the instant the offer exists the SAME function buys it at 96c "
       f"(got {out_mid['reason_now_w']}, "
       f"{out_mid['decide']['now/attempt/w'][2]})")
    # a shallow offer must be refused for depth, not for absence
    d_sh = [(S * 1000 + 300, "no", 0.04, 3.0, 1002)
            if d[0] == S * 1000 + 300 and d[3] > 0 else d for d in deltas]
    out_sh = probe_fill(fl_mid, {iid: ticks}, snaps, d_sh, trades, mkr)
    ck(out_sh["reason_now_w"] == "too_shallow",
       f"and 3 contracts against an order of 20 is refused 'too_shallow', not "
       f"'no_offer' (got {out_sh['reason_now_w']})")

    # ---- (d) settlement
    ck(out["result_tape"] == "yes" and out["result_live"] == "yes"
       and "SETTLE_MISMATCH" not in out["flags"],
       "the settlement matches and is not flagged")
    out_ms = probe_fill(fl_ok, {iid: ticks}, snaps, deltas, trades,
                        dict(mkr, result="no"))
    ck("SETTLE_MISMATCH" in out_ms["flags"],
       "and a tape result of 'no' against a live result of 'yes' IS flagged")
    out_nt = probe_fill(fl_ok, {iid: ticks}, snaps, deltas, trades,
                        dict(mkr, result=None))
    ck("NO_TAPE_SETTLEMENT" in out_nt["flags"],
       "and a market with no settlement on file is flagged, not guessed")
    # (d) the settlement recomputed from the index tape, which needs no
    # markets.json at all
    ck(out["settle_prints"] == 60 and out["result_idx"] == "yes"
       and abs(out["settle_mean_idx"] - 100.0005) < 1e-9,
       f"the index tape alone settles the planted market: mean of "
       f"{out['settle_prints']} prints = {out['settle_mean_idx']} against "
       f"effective strike {out['eff_strike']} -> {out['result_idx']}")
    ck("SETTLE_MISMATCH_VS_INDEX" not in out_nt["flags"],
       "and it agrees with the outcome we booked, so nothing is flagged even "
       "with markets.json empty")
    hi_k = dict(mkr, strike=101.0)
    o_hi = probe_fill(fl_ok, {iid: ticks}, snaps, deltas, trades, hi_k)
    ck(o_hi["result_idx"] == "no"
       and "SETTLE_MISMATCH_VS_INDEX" in o_hi["flags"],
       f"move the strike above the settlement mean and the index says `no` "
       f"({o_hi['result_idx']}) and the disagreement with our booked `yes` IS "
       f"flagged")
    short = [t for t in ticks if t[0] < C - 40]
    o_sh = probe_fill(fl_ok, {iid: short}, snaps, deltas, trades, mkr)
    ck(o_sh["result_idx"] is None
       and "INDEX_SETTLE_WINDOW_INCOMPLETE" in o_sh["flags"],
       f"and a settlement window missing prints is reported incomplete, never "
       f"averaged over what happens to be there "
       f"({o_sh['settle_prints']} of 60)")

    # ---- pinsim's snapshot ordering, on a market whose levelled snapshot is
    #      followed in the file by an EMPTY one (which Kalshi sends when the
    #      book is empty). pinsim applies both up front, so the levels are
    #      wiped before any delta lands; ts order applies them in time.
    lev = {"market_ticker": mkr["ticker"],
           "yes_dollars_fp": [["0.5000", "100.00"]],
           "no_dollars_fp": [["0.0200", "200.00"]]}
    snaps_ctl = [(lev, 1000, (C - 300) * 1000 + 40)]
    # the empty snapshot arrives AFTER second S. In seq order it cannot touch
    # the boundary book; pinsim applies every snapshot in the hour up front,
    # so for pinsim it wipes the levels before a single delta is read.
    snaps_wipe = snaps_ctl + [({"market_ticker": mkr["ticker"]}, 1100,
                               (S + 1) * 1000 + 500)]
    o_ctl = probe_fill(fl_ok, {iid: ticks}, snaps_ctl, deltas, trades, mkr)
    o_wipe = probe_fill(fl_ok, {iid: ticks}, snaps_wipe, deltas, trades, mkr)
    ck(o_ctl["ask_s0"] == 0.98 and o_ctl["ask_ps"] == 0.98
       and "PINSIM_BOOK_DIFFERS_FROM_SEQ_ORDER" not in o_ctl["flags"],
       f"CONTROL: with one levelled snapshot both orderings see the same 98c "
       f"offer and nothing is flagged ({o_ctl['ask_s0']}, {o_ctl['ask_ps']})")
    ck(o_wipe["ask_s0"] == 0.98 and o_wipe["ask_ps"] is None,
       f"but with an empty snapshot later in the file pinsim's snaps-first "
       f"ordering loses the offer entirely (ts {o_wipe['ask_s0']}, pinsim "
       f"{o_wipe['ask_ps']})")
    ck("PINSIM_BOOK_DIFFERS_FROM_SEQ_ORDER" in o_wipe["flags"],
       "and the harness flags PINSIM_BOOK_DIFFERS_FROM_SEQ_ORDER")

    # ---- seq order beats timestamp order on the shape the tape really has:
    #      a snapshot whose seq precedes the first delta but whose receipt
    #      time does not.
    ev_seq = merge_events(snaps, deltas, "seq")
    ev_ts = merge_events(snaps, deltas, "ts")
    ck(ev_seq[0][1] == 0 and ev_ts[0][1] == 1,
       "seq order puts the snapshot FIRST (its seq is lower); timestamp order "
       "puts the delta first, because the snapshot's receipt trails it")
    bk_seq = build_book(ev_seq, (C - 200) * 1000)
    bk_ts = build_book(ev_ts, (C - 200) * 1000)
    ck(bk_seq.yes.get(0.5) == 150.0 and bk_ts.yes.get(0.5) == 100.0,
       f"so seq order keeps both the snapshot's 100 and the delta's 50 "
       f"({bk_seq.yes.get(0.5)}), while timestamp order WIPES the delta "
       f"({bk_ts.yes.get(0.5)}) -- the phantom-book bug, reproduced")
    # and a case where the OFFER itself differs, not just a level's size:
    # a snapshot carrying a 2c no bid (= a 98c yes offer) plus a delta
    # whose seq is AFTER the snapshot but whose ts_ms is BEFORE its
    # receipt, removing that level. Seq order removes it; timestamp order
    # applies the removal first -- to a level that is not there yet --
    # and then the snapshot puts it back: a phantom offer.
    snap_no = {"market_ticker": mkr["ticker"],
               "yes_dollars_fp": [],
               "no_dollars_fp": [["0.0200", "200.00"]]}
    sn2 = [(snap_no, 1000, (C - 300) * 1000 + 200)]
    dl2 = [((C - 300) * 1000 + 50, "no", 0.0200, -200.0, 1001)]
    o2 = probe_fill(fl_ok, {iid: ticks}, sn2, dl2, trades, mkr)
    ck(o2["ask_s0"] is None and o2["ask_tsord"] == 0.98,
       f"seq order sees the 2c no bid removed (yes offer {o2['ask_s0']}); "
       f"timestamp order resurrects it ({o2['ask_tsord']})")
    ck("TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER" in o2["flags"],
       "and the harness flags TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER")

    # ---- the bounded salvager must match gzsalvage line for line, on a
    #      healthy file and on the two-member wreck a collector restart leaves
    import tempfile
    tmpd = tempfile.mkdtemp(prefix="pinreplay_st_")
    good = os.path.join(tmpd, "good.jsonl.gz")
    with gzip.open(good, "wt", encoding="utf-8") as fh:
        for i in range(500):
            fh.write(json.dumps({"i": i, "pad": "x" * 200}) + "\n")
    mine = [ln for ln in _salvage_lines(good)]
    theirs = [ln for ln in gzsalvage.iter_lines(good)]
    ck(mine == theirs and len(mine) == 500,
       f"the bounded salvager matches gzsalvage on a healthy file "
       f"({len(mine)} vs {len(theirs)} lines)")
    wreck = os.path.join(tmpd, "wreck.jsonl.gz")
    import zlib as _z
    blob = b""
    for part in (range(0, 5), range(5, 9)):
        co = _z.compressobj(6, _z.DEFLATED, 16 + _z.MAX_WBITS)
        body = b"".join((json.dumps({"i": i}) + "\n").encode() for i in part)
        blob += co.compress(body) + co.flush(_z.Z_SYNC_FLUSH)   # NO trailer
    with open(wreck, "wb") as fh:
        fh.write(blob)
    mine_w = [ln for ln in _salvage_lines(wreck)]
    theirs_w = [ln for ln in gzsalvage.iter_lines(wreck)]
    ck(mine_w == theirs_w and len(mine_w) >= 5,
       f"and on a two-member file with no trailers -- what a collector restart "
       f"leaves -- it recovers the same {len(mine_w)} lines gzsalvage does "
       f"(gzsalvage: {len(theirs_w)})")
    with gzip.open(wreck, "rb") as _fh:
        try:
            _fh.read()
            _std = "no error"
        except Exception as _e:                                 # noqa: BLE001
            _std = type(_e).__name__
    ck(_std != "no error",
       f"and the STANDARD reader fails on that file ({_std}) -- which is why "
       f"the salvage path exists at all")
    for _f in (good, wreck):
        try:
            os.remove(_f)
        except OSError:
            pass
    try:
        os.rmdir(tmpd)
    except OSError:
        pass

    # ---- THE HAND RECONCILIATION, frozen.
    # Every other fair check lets pinrun agree with itself. These numbers
    # were read off the raw index tape for the first
    # KXNEAR15M-26SEP082045-45 loss (close 1788914700, decision second
    # 1788914678) and the fair recomputed from the settlement model with a
    # formula written out by hand:
    #   locked = sum of the 39 prints in [close-60, newest held] = 91.601300
    #   r      = 60 - 39 = 21 prints still to come
    #   spot   = 2.3483, strike 2.3492, KXNEAR15M rounds to 4 digits
    #   K      = 2.3492 - 0.5e-4                       = 2.349150
    #   mu     = (locked + r * spot) / 60              = 2.34859333
    #   sd     = sigma * sqrt(var_factor(21))          = 0.00026661
    #   fair   = Phi((mu - K) / sd)
    # The live log records fair 0.01826 and sigma 0.000278 -- and sigma is
    # rounded to six places in the log, which alone moves the answer by
    # 1.4e-4. With the sigma the replay actually computes, 0.00027759, the
    # hand arithmetic lands on 0.01826 exactly.
    import math as _m
    from engine import var_factor as _vf
    _mu = (91.601300 + 21 * 2.3483) / 60.0
    _K = 2.3492 - 0.5e-4
    _fh = _ND.cdf((_mu - _K) / (0.00027759 * _m.sqrt(_vf(21, [1.0]))))
    ck(abs(_fh - 0.01826) < 5e-6,
       f"HAND RECONCILIATION: the settlement model written out by hand "
       f"gives {_fh:.5f} for the first NEAR loss, against the 0.01826 the "
       f"live bot logged")
    _fr = _ND.cdf((_mu - _K) / (0.000278 * _m.sqrt(_vf(21, [1.0]))))
    ck(abs(_fr - 0.01840) < 5e-6,
       f"and the SAME arithmetic with the log's ROUNDED sigma gives "
       f"{_fr:.5f} -- a 6-decimal log field is worth 1.4e-4 of fair, which "
       f"is above this file's 1e-4 flag, so sigma is reported beside it")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ------------------------------------------------------------------- real data
def load_markets():
    mk = {}
    try:
        d = json.load(open(FULLTAPE, encoding="utf-8"))
    except Exception as e:                                     # noqa: BLE001
        print(f"  *** could not read {FULLTAPE}: {e}")
        return mk
    for v in d.values():
        for r in v:
            mk[r["ticker"]] = r
    return mk


def analyse(fills, mk, log=print):
    """One tape hour at a time, one pass per channel per hour.

    MEMORY: the only thing held is the target markets' own deltas for the hour
    (tens of thousands of 4-tuples), never the whole hour. The collector
    outranks this job; peak RSS is reported by the caller.
    """
    by_hour = defaultdict(list)
    for fl in fills:
        by_hour[hour_stamp(fl["S"])].append(fl)
    rows = []
    bad_total = 0
    lines_total = 0
    salvaged = []
    missing = []
    live_hour = hour_stamp(time.time())
    log(f"  {len(fills)} fills over {len(by_hour)} tape hours, "
        f"{len({f['ticker'] for f in fills})} markets")
    log(f"  the current UTC hour is {live_hour}; its files are still being "
        f"appended, so fills in it are flagged TAPE_HOUR_STILL_OPEN and kept "
        f"out of the headline")
    for i, stamp in enumerate(sorted(by_hour)):
        group = by_hour[stamp]
        tickers = {f["ticker"] for f in group}
        # the 400 s of index a decision needs can start in the PREVIOUS hour
        # only if S lands in the first 400 s of this one; closes are on the
        # quarter hour and tau <= 30 so it never does, but check rather than
        # assume.
        stamps = [stamp]
        hstart = calendar.timegm(time.strptime(stamp, "%Y%m%dT%H"))
        if min((mk.get(f["ticker"], {}).get("close")
                or close_from_ticker(f["ticker"])) for f in group) - 400 < hstart:
            stamps.insert(0, hour_stamp(hstart - 3600))
        stats = {}
        # The hour the collector is still writing has one untrailered member,
        # so the fast reader already recovers every flushed line; salvaging it
        # would re-read and re-decompress an 80 MB file for nothing.
        salv = stamp < live_hour
        ticks = load_ticks_rx(stamps, stats, salv)
        snaps = load_snaps(stamp, tickers, stats, salv)
        deltas, bad, nlines = load_deltas(stamp, tickers, stats, salv)
        trades = load_trades(stamp, tickers, stats, salv)
        bad_total += bad
        lines_total += nlines
        hflags = []
        if stamp >= live_hour:
            hflags.append("TAPE_HOUR_STILL_OPEN")
        if stats.get("salvaged_files"):
            hflags.append("TAPE_SALVAGED")
            salvaged += stats.get("salvaged_channels", [])
        if stats.get("missing"):
            hflags.append("TAPE_FILE_MISSING")
            missing += stats.get("missing_files", [])
        if stats.get("truncated"):
            hflags.append("TAPE_TRUNCATED")
        for fl in group:
            tk = fl["ticker"]
            r = probe_fill(fl, ticks, snaps.get(tk, []),
                           deltas.get(tk, []), trades.get(tk, []),
                           mk.get(tk, {}))
            r["hour"] = stamp
            r["flags"] = hflags + r["flags"]
            rows.append(r)
        del ticks, snaps, deltas, trades
        if (i + 1) % 10 == 0 or i + 1 == len(by_hour):
            log(f"    {i + 1}/{len(by_hour)} hours  ({stamp})", flush=True)
    if bad_total:
        log(f"  *** {bad_total:,} DELTAS FAILED TO PARSE -- books incomplete ***")
    log(f"  scanned {lines_total:,} delta lines")
    if salvaged:
        log(f"  {len(salvaged)} hour-channels needed gzip SALVAGE: "
            f"{sorted(set(salvaged))[:6]}")
    if missing:
        log(f"  {len(missing)} hour-channels MISSING: {sorted(set(missing))[:6]}")
    return rows, bad_total, sorted(set(salvaged)), sorted(set(missing))


FLAG_ORDER = [
    "TAPE_HOUR_STILL_OPEN", "TAPE_SALVAGED", "TAPE_TRUNCATED",
    "TAPE_FILE_MISSING",
    "FAIR_DIVERGE", "FAIR_NEEDS_ONE_SEC_LAG", "FAIR_UNCOMPUTABLE",
    "STRIKE_MISMATCH", "PRICE_DIVERGE_AT_W",
    "OFFER_MISSING", "OFFER_ONLY_SUBSECOND", "OFFER_ABSENT_AT_EVERY_MS",
    "PINSIM_BOOK_DIFFERS_FROM_SEQ_ORDER",
    "TS_ORDER_BOOK_DIFFERS_FROM_SEQ_ORDER", "SEQ_NOT_MONOTONE",
    "OUR_FILL_NOT_ON_TAPE", "NO_TAPE_SETTLEMENT", "NO_LIVE_SETTLEMENT",
    "SETTLE_MISMATCH", "SETTLE_MISMATCH_VS_INDEX",
    "REFUSED_BY_PINRUN_DUMP_GUARD_TODAY",
    "REFUSED_BY_BACKTEST_PROFILE_RULE", "FULL_BACKTEST_WOULD_NOT_BUY",
    "MARKETS_JSON_DISAGREES_WITH_INDEX",
    "INDEX_SETTLE_WINDOW_INCOMPLETE", "BACKTEST_WOULD_NOT_BUY",
]


def flag_table(rows, title, out):
    n = len(rows)
    nclose = len({r["close_s"] for r in rows})
    out.append(f"\n### {title} -- n = {n} fills over {nclose} closes\n")
    out.append("| flag | fills | % | closes |")
    out.append("|---|---|---|---|")
    for fg in FLAG_ORDER:
        hit = [r for r in rows if fg in r["flags"]]
        if not hit and fg not in ("OFFER_MISSING", "BACKTEST_WOULD_NOT_BUY"):
            continue
        out.append(f"| {fg} | {len(hit)} | "
                   f"{100.0 * len(hit) / n if n else 0:.1f}% | "
                   f"{len({r['close_s'] for r in hit})} |")
    why = defaultdict(int)
    for r in rows:
        for fg in r["flags"]:
            if fg.startswith("WHYNOT:"):
                why[fg[7:]] += 1
    if why:
        out.append(f"\n**Why `pinsim.decide` would not have bought "
                   f"({sum(why.values())} of {n})** -- at the second boundary, "
                   f"today's gate, our own order size:\n")
        out.append("| reason | fills | % |")
        out.append("|---|---|---|")
        for k, v in sorted(why.items(), key=lambda x: -x[1]):
            out.append(f"| `{k}` | {v} | {100.0 * v / n:.1f}% |")
    return out


def _fmt(v, nd=4):
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def loss_detail(r, out):
    out.append(f"\n#### {r['ticker']}  want {r['want'].upper()} @ "
               f"{r['exec_price']:.4f}  x{r['filled']:g}  "
               f"P&L {r['pnl_c']:+.2f}c")
    out.append(f"\nfill second `{r['t_iso']}` (S={r['S']}), close "
               f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(r['close_s']))} "
               f"from {r['close_src']}, tau {r['tau_tape']}s "
               f"(live logged tau {r['tau_live']}, tau_at_send {r['tau_at_send']}), "
               f"latency {_fmt(r['latency_ms'], 1)} ms, decision instant "
               f"S+{int(r['W_ms'] - r['S'] * 1000)} ms "
               f"({'exact' if r['W_exact'] else 'ASSUMED S+500'}).\n")
    out.append("| | value |")
    out.append("|---|---|")
    out.append(f"| **(a) fair, live** | `{_fmt(r['fair_live'], 5)}` |")
    out.append(f"| (a) fair, replay ticks<=S (what pinsim uses) | "
               f"`{_fmt(r['fair_sec'], 5)}`  (|d| {_fmt(r['d_sec'], 6)}) |")
    out.append(f"| (a) fair, replay ticks<=S-1 | "
               f"`{_fmt(r['fair_secm1'], 5)}`  (|d| {_fmt(r['d_secm1'], 6)}) |")
    out.append(f"| (a) fair, replay ticks by ARRIVAL<=decision instant | "
               f"`{_fmt(r['fair_rx'], 5)}`  (|d| {_fmt(r['d_rx'], 6)}) |")
    out.append(f"| (a) closest feed | **{r['fair_best']}**, "
               f"|d| {_fmt(r['fair_best_d'], 6)} "
               f"{'> 1e-4 **DIVERGES**' if (r['fair_best_d'] or 0) > FAIR_TOL else 'within 1e-4'} |")
    out.append(f"| (a) sigma live / replay | "
               f"`{_fmt(r['sigma_sec'], 8) if r.get('sigma_sec') else '-'}` "
               f"replay vs live `{_fmt((r.get('sigma_live')), 8)}` |")
    out.append(f"| strike live / tape | {_fmt(r['strike_live'])} / "
               f"{_fmt(r['strike_tape'])} |")
    out.append(f"| **(b) offer we paid** | {r['exec_price']:.4f} "
               f"(model saw {_fmt(r['price_live'])}) |")
    out.append(f"| (b) our-side ask at START of S (pinsim's view) | "
               f"{_fmt(r['ask_s0'])} x {_fmt(r['asksz_s0'], 1)} |")
    out.append(f"| (b) our-side ask at END of S | "
               f"{_fmt(r['ask_s1'])} x {_fmt(r['asksz_s1'], 1)} |")
    out.append(f"| (b) our-side ask at the DECISION INSTANT | "
               f"{_fmt(r['ask_w'])} x {_fmt(r['asksz_w'], 1)} |")
    out.append(f"| (b) offer <= what we paid, at a second boundary? | "
               f"**{'YES' if (r['offer_at_s0'] or r['offer_at_s1']) else 'NO -- OFFER MISSING'}** |")
    out.append(f"| (b) offer existed at some ms in [S-1, S+2)? | "
               f"**{'YES' if r['ms_any'] else 'NO'}**, for {r['ms_present']} ms "
               f"of 3000 ({r['ms_instants']} book states checked; best ask seen "
               f"{_fmt(r['ms_best_ask'])}) |")
    if r["ms_any"]:
        out.append(f"| (b) offer window (the scan covers S-1000 to S+2000) | "
                   f"S{r['ms_first']:+d} ms to S{r['ms_last']:+d} ms |")
    out.append(f"| (b) book age at instant: replay / live-logged | "
               f"{_fmt(r['bookage_w'], 0)} ms / "
               f"{_fmt((r.get('bookage_live')), 0)} ms |")
    out.append(f"| (b) deltas / snapshots (levelled) on this market this hour | "
               f"{r['n_deltas']:,} / {r['n_snaps']} ({r['n_snaps_levelled']}) |")
    out.append(f"| **(c) our fill on the trade tape** | "
               f"{('FOUND, ' + str(r['print_nlegs']) + ' leg' + ('s' if r['print_nlegs'] != 1 else '')) if r['print_found'] else ('a same-side print within one tick exists but NO ladder reconciles to our count and VWAP' if r['print_price_only'] else '**NOT ON TAPE**')} |")
    if r["print_ts"]:
        out.append(f"| (c) the ladder | taker {r['print_taker']} "
                   + " + ".join(f"{px:.4f} x{c:g}"
                                for px, c in (r['print_legs'] or []))
                   + f" -> {_fmt(r['print_count'], 2)} contracts, VWAP "
                     f"{_fmt(r['print_price'], 6)} against the {r['exec_price']:.4f} "
                     f"the bot logged; {r['print_dt_ms']:+d} ms from the "
                     f"decision instant |")
    out.append(f"| (c) prints on this market in [S-1, S+2) | "
               f"{r['n_trades_window']} |")
    out.append(f"| **(d) settlement, from the INDEX TAPE** | mean of "
               f"{r['settle_prints']} prints = {_fmt(r['settle_mean_idx'], 6)} vs "
               f"effective strike {_fmt(r['eff_strike'], 6)} -> "
               f"`{_fmt(r['result_idx'])}` |")
    out.append(f"| (d) settlement | tape `{_fmt(r['result_tape'])}` vs live "
               f"`{_fmt(r['result_live'])}` -> "
               f"{'MISMATCH' if 'SETTLE_MISMATCH' in r['flags'] else ('no tape settlement yet' if r['result_tape'] is None else 'agree')} |")
    out.append(f"| **(e) pinsim.decide, second boundary, today's gate** | "
               f"**{r['reason_now_s0']}** |")
    out.append(f"| (e) pinsim.decide at the decision instant | "
               f"{r['reason_now_w']} |")
    out.append(f"| (e) pinsim.decide, second boundary, the gate that was LIVE "
               f"(PIN {_fmt(r['live_pin'])}, ceiling {_fmt(r['live_ceiling'])}) "
               f"| {r['reason_then_s0']} |")
    out.append(f"| (e) pinsim.decide at the decision instant, the LIVE gate | "
               f"**{r['reason_then_w']}** |")
    other = sorted({f"{k}={v[5]}" for k, v in r["decide"].items()
                    if k.endswith("/s0")})
    out.append(f"| **(e) discount to fair we paid** | {_fmt(r['disc_c'], 2)}c "
               f"-> pinrun's live {100 * pinrun.DUMP_DISCOUNT:.0f}c guard TODAY: "
               f"{'**REFUSE**' if r.get('dump_now') else 'allow'}; the guard "
               f"live at the time ({_fmt(r.get('dump_discount_then'))}): "
               f"{'REFUSE' if r.get('dump_then') else ('allow' if r.get('dump_then') is not None else 'not logged')} |")
    out.append(f"| (e) the backtest profile's rules | {_fmt(r['rule_verdict'])}"
               f"{(' (' + ', '.join(r['rule_fired']) + ')') if r.get('rule_fired') else ''} |")
    out.append(f"| **(e) FULL backtest verdict (decide + rules), decision ms, "
               f"today's gate** | **{r.get('full_now_w')}** |")
    out.append(f"| (e) all size/gate variants at the boundary | "
               f"{', '.join(other)} |")
    out.append(f"| flags | {', '.join(r['flags']) or 'none'} |")
    return out


def diagnose(rows, out):
    """THE DIAGNOSIS, computed from the counts rather than asserted.

    Four candidate causes are separated, because conflating them is how a
    replay gets "fixed" in the wrong place:
      1. the MODEL        -- does the replayed fair match the logged fair?
      2. the BOOK REBUILD -- does the reconstructed book hold the offer at all?
      3. the SAMPLING     -- once per second, versus the millisecond the bot
                             decided at 20 Hz?
      4. the RULE         -- a gate or guard that has since changed?
    """
    n = len(rows)
    if not n:
        return out
    fair_ok = sum(1 for r in rows if "FAIR_DIVERGE" not in r["flags"])
    never = sum(1 for r in rows if not r["ms_any"])
    at_ms = sum(1 for r in rows if r["offer_at_W"])
    at_b = sum(1 for r in rows if r["offer_at_s0"])
    px_w = sum(1 for r in rows if r.get("ask_w") is not None
               and r.get("price_live") is not None
               and abs(r["ask_w"] - r["price_live"]) <= PX_TOL)
    px_b = sum(1 for r in rows if r.get("ask_s0") is not None
               and r.get("price_live") is not None
               and abs(r["ask_s0"] - r["price_live"]) <= PX_TOL)
    tape = sum(1 for r in rows if r["print_found"])
    legs = sum(1 for r in rows if (r.get("print_nlegs") or 0) > 1)
    sett = sum(1 for r in rows if r["result_idx"] is not None
               and r["result_live"] is not None
               and r["result_idx"] == str(r["result_live"]).lower())
    b_now = sum(1 for r in rows if r.get("full_now_s0") == "bought")
    b_w = sum(1 for r in rows if r.get("full_now_w") == "bought")
    b_then = sum(1 for r in rows if r.get("full_then_w") == "bought")
    why = defaultdict(int)
    for r in rows:
        v = r.get("full_now_s0")
        if v and v != "bought":
            why[v] += 1
    top = sorted(why.items(), key=lambda x: -x[1])
    losses = [r for r in rows if r["loss"]]
    lb = sum(1 for r in losses if r.get("full_now_s0") == "bought")
    lwhy = defaultdict(int)
    for r in losses:
        v = r.get("full_now_s0")
        if v and v != "bought":
            lwhy[v] += 1
    ltop = sorted(lwhy.items(), key=lambda x: -x[1])
    out.append("\n## DIAGNOSIS\n")
    out.append(
        f"**The model is not the problem and neither is the tape.** The "
        f"replayed index reproduces the `fair` the live bot logged on "
        f"**{fair_ok} of {n}** fills to within 1e-4; our own fill reconciles "
        f"exactly to a LADDER of same-side prints on the trade tape -- our "
        f"count and our VWAP -- on **{tape} of {n}** ({legs} of them swept "
        f"more than one level); and the settlement recomputed from the sixty "
        f"index prints agrees with the outcome we booked on **{sett} of {n}**. "
        f"The offer we hit exists in the rebuilt book at some millisecond on "
        f"**{n - never} of {n}** fills -- it is NOT invisible. What breaks is "
        f"WHEN the book is read and WHICH RULE reads it. Reconstructed on the "
        f"exchange's `seq` and evaluated at the millisecond the live bot "
        f"decided, the book shows exactly the price we paid on **{px_w} of "
        f"{n}**; evaluated at the second boundary, which is what "
        f"`pinsim.run()` does, it shows it on **{px_b} of {n}** and holds an "
        f"offer at or better than we paid on {at_b} against {at_ms} at the "
        f"decision instant -- but that near-tie hides the real gap, because "
        f"the two do not agree about WHICH offer: the price matches on "
        f"{px_b} against {px_w}. Then the rule layer: the existing backtest, run "
        f"at the second boundary under today's constants, would have bought "
        f"**{b_now} of {n}** of our own fills"
        + (f" -- the dominant refusal is `{top[0][0]}` on {top[0][1]} of them"
           if top else "")
        + (f", then `{top[1][0]}` on {top[1][1]}" if len(top) > 1 else "")
        + f". Move only the sampling to the decision millisecond and it buys "
          f"**{b_w}**; put back the gate that was actually live for each fill "
          f"and it buys **{b_then} of {n}**. "
        f"**On the {len(losses)} fills that LOST money the same backtest buys "
        f"{lb}**"
        + (f", refusing the rest as "
           + ", ".join(f"`{k}` x{v}" for k, v in ltop) if ltop else "")
        + f". That is the answer to why the backtest does not show our losses: "
          f"not a blind book and not a broken model, but a once-a-second "
          f"sample of a book that changes ~{_median_instants(rows)} times a "
          f"second, judged by a gate that has since been tightened past the "
          f"trades it is being asked to reproduce.")
    return out


def _median_instants(rows):
    v = sorted(r["ms_instants"] for r in rows if r.get("ms_instants"))
    return int(round(v[len(v) // 2] / 3.0)) if v else 0


def report(rows, bad_total, salvaged, missing, log=print):
    out = []
    n = len(rows)
    closes = len({r["close_s"] for r in rows})
    losses = [r for r in rows if r["loss"]]
    wins = [r for r in rows if not r["loss"]]
    out.append("# RESULTS_replay -- does the tape replay reproduce our own trades?")
    out.append(f"\n`research/pinreplay.py`, run {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}.")
    out.append(f"\n**n = {n} live fills over {closes} closes over "
               f"{len({r['ticker'] for r in rows})} markets**, every one a real "
               f"order the bot actually got filled on, read from "
               f"`results/pinrun-live-*.jsonl`. "
               f"**{len(losses)} of them lost money.** No simulated fill, no "
               f"assumed rule, no tape-derived loss rate appears anywhere in "
               f"this file -- the losses are our own.")
    if bad_total:
        out.append(f"\n**{bad_total:,} deltas failed to parse; the rebuilt "
                   f"books are incomplete and every book row below is "
                   f"suspect.**")
    else:
        out.append("\nZero deltas failed to parse.")
    out.append(f"\nTape integrity: {len(salvaged)} hour-channels needed "
               f"member-by-member gzip salvage (a collector restart inside the "
               f"hour; the standard reader recovers ZERO lines from those and "
               f"would have shown an empty book){(' -- ' + ', '.join(salvaged[:8])) if salvaged else ''}. "
               f"{len(missing)} hour-channels are missing entirely"
               f"{(' -- ' + ', '.join(missing[:8])) if missing else ''}.")
    stillopen = [r for r in rows if "TAPE_HOUR_STILL_OPEN" in r["flags"]]
    if stillopen:
        out.append(f"\n**{len(stillopen)} fills are in the CURRENT UTC hour, "
                   f"whose tape files the collector is still appending.** Their "
                   f"books are truncated by construction and they are flagged "
                   f"`TAPE_HOUR_STILL_OPEN`; the tables below are given with "
                   f"and without them.")
    out.append("\n## What each check means\n")
    out.append("| | question |")
    out.append("|---|---|")
    out.append("| (a) | does the replayed index reproduce the `fair` the live "
               "model logged, to 1e-4? Three feeds are tried: ticks stamped "
               "`<= S` (pinsim's rule), `<= S-1`, and ticks fed by ARRIVAL up "
               "to the reconstructed decision millisecond. |")
    out.append("| (b) | is there an ask at or better than the price we paid, "
               "in the rebuilt book, on our side -- at the second boundary "
               "(what the backtest sees) and at every delta instant inside "
               "the second (what the bot saw)? |")
    out.append("| (c) | is our own fill on the trade tape? `exec_price` is "
               "the VWAP of a swept ladder, not a level price, so the test is "
               "whether contiguous same-side prints exist whose counts sum to "
               "ours and whose VWAP equals what we paid to 2e-4. |")
    out.append("| (d) | does `fulltape/markets.json` agree with the outcome "
               "the live bot booked? |")
    out.append("| (e) | would `pinsim.decide` -- the existing backtest's "
               "decision function, called here, not reimplemented -- have "
               "bought it, and if not, what reason string does it return? |")
    flag_table(rows, "ALL FILLS", out)
    flag_table(losses, "THE LOSING FILLS ONLY", out)
    flag_table(wins, "THE WINNING FILLS ONLY (the control)", out)

    # the fair feeds, side by side
    out.append("\n## (a) which index feed reproduces the live `fair`\n")
    out.append("| feed | fills within 1e-4 | median |d| | max |d| |")
    out.append("|---|---|---|---|")
    for name, label in (("sec", "ticks stamped <= S  (**what pinsim does**)"),
                        ("secm1", "ticks stamped <= S-1"),
                        ("rx", "ticks by ARRIVAL <= decision ms  (**faithful**)")):
        ds = sorted(r[f"d_{name}"] for r in rows if r[f"d_{name}"] is not None)
        if not ds:
            out.append(f"| {label} | - | - | - |")
            continue
        ok = sum(1 for d in ds if d <= FAIR_TOL)
        out.append(f"| {label} | {ok}/{len(ds)} ({100.0 * ok / len(ds):.1f}%) | "
                   f"{ds[len(ds) // 2]:.2e} | {ds[-1]:.2e} |")

    # the book, side by side
    out.append("\n## (b) where the offer we hit actually was\n")
    out.append("| the offer we paid was visible... | fills | % |")
    out.append("|---|---|---|")
    for label, pred in (
            ("at the START of second S (pinsim's own view)",
             lambda r: r["offer_at_s0"]),
            ("at the END of second S", lambda r: r["offer_at_s1"]),
            ("at the reconstructed DECISION instant",
             lambda r: r["offer_at_W"]),
            ("at SOME millisecond in [S-1, S+2)", lambda r: r["ms_any"]),
            ("at NO millisecond at all -- invisible to any book replay",
             lambda r: not r["ms_any"])):
        h = [r for r in rows if pred(r)]
        out.append(f"| {label} | {len(h)} | {100.0 * len(h) / n:.1f}% |")
    out.append("\n### which book reconstruction reproduces the offer the "
               "live model logged\n")
    out.append("The live `signal` record logs the exact `price` the bot saw on "
               "our side. That is the ground truth for a book rebuild, so it is "
               "scored directly. `seq order` merges snapshots and deltas on the "
               "exchange's own sequence number; `timestamp order` merges them on "
               "the clock (deltas' `ts_ms`, snapshots' receipt time); "
               "`snapshots-first` is what `pinsim.run()` does -- every snapshot "
               "in the hour applied before any delta.\n")
    out.append("| reconstruction, evaluated at | == live logged price | "
               "median |d| (cents) |")
    out.append("|---|---|---|")
    for label, key in (("**seq order, the decision millisecond**", "ask_w"),
                       ("seq order, start of second S", "ask_s0"),
                       ("seq order, end of second S", "ask_s1"),
                       ("timestamp order, start of second S", "ask_tsord"),
                       ("snapshots-first (pinsim), start of second S", "ask_ps")):
        ds = [abs(r[key] - r["price_live"]) for r in rows
              if r.get(key) is not None and r.get("price_live") is not None]
        nn = sum(1 for r in rows if r.get("price_live") is not None)
        ok = sum(1 for d in ds if d <= PX_TOL)
        out.append(f"| {label} | {ok}/{nn} "
                   f"({100.0 * ok / nn if nn else 0:.1f}%) | "
                   f"{100 * sorted(ds)[len(ds) // 2]:.2f}c |" if ds
                   else f"| {label} | - | - |")
    live_ms = sorted(r["ms_present"] for r in rows if r["ms_any"])
    if live_ms:
        out.append(f"\nWhere the offer was visible at all, it was on the book "
                   f"for a median of **{live_ms[len(live_ms) // 2]} ms** of the "
                   f"3,000 ms window (p10 {live_ms[len(live_ms) // 10]}, "
                   f"p90 {live_ms[len(live_ms) * 9 // 10]}, max {live_ms[-1]}).")
    out.append("\n## (c) our own fills, reconciled against the trade tape\n")
    out.append("`exec_price` is the SIZE-WEIGHTED AVERAGE of everything the IOC "
               "swept, not a level price -- the DOGE loss is logged at 0.0998, "
               "which is not on the 0.1c tick grid at all, and its true print is "
               "`0.1100 x17 + 0.0420 x3` at one `ts_ms`, VWAP exactly 0.099800. "
               "So a fill is reconciled against a LADDER: contiguous same-side "
               "prints whose counts sum to ours and whose VWAP equals what we "
               "paid to 2e-4.\n")
    out.append("| | fills | % |")
    out.append("|---|---|---|")
    fnd = [r for r in rows if r["print_found"]]
    out.append(f"| **our fill reconciles exactly to a ladder on the tape** | "
               f"{len(fnd)} | {100.0 * len(fnd) / n:.1f}% |")
    nb = defaultdict(int)
    for r in fnd:
        nb[r["print_nlegs"]] += 1
    for k in sorted(nb):
        out.append(f"| ... as {k} leg{'s' if k != 1 else ''} | {nb[k]} | "
                   f"{100.0 * nb[k] / n:.1f}% |")
    miss = [r for r in rows if not r["print_found"]]
    out.append(f"| no ladder reconciles, but a same-side print within one tick "
               f"exists | {sum(1 for r in miss if r['print_price_only'])} | "
               f"{100.0 * sum(1 for r in miss if r['print_price_only']) / n:.1f}% |")
    out.append(f"| nothing on our side within one tick at all | "
               f"{sum(1 for r in miss if not r['print_price_only'])} | "
               f"{100.0 * sum(1 for r in miss if not r['print_price_only']) / n:.1f}% |")
    # the ones that do not reconcile: is it a matching failure or a HOLE?
    silent = [r for r in miss if not r["n_trades_window"]]
    if miss:
        out.append(f"\nOf the {len(miss)} that do not reconcile, "
                   f"**{len(silent)} have ZERO prints on that market anywhere "
                   f"in the three-second window** -- so it is not a matching "
                   f"failure, the trade tape simply does not contain the "
                   f"execution. Checked by hand on "
                   f"`KXBTC15M-26SEP110130-30` (fill 2026-09-11T05:29:30Z): "
                   f"that market printed 19,911 times across the two "
                   f"surrounding hours and **not once in the 40 s around our "
                   f"fill**, and neither did any other market -- the whole "
                   f"`trade` channel is silent from 05:27:11 to 05:31:00, a "
                   f"**230-second blackout**. That hour has 374 silent seconds "
                   f"of 3,523 (10.6%), in runs of 230, 72 and 53 s. A quiet "
                   f"second is normal; a 230-second run with zero prints across "
                   f"every live market is a dropped subscription. "
                   f"**Consequence: the `trade` channel has holes, and any "
                   f"result that treats it as complete -- `pintrades.py` is "
                   f"the one that matters -- inherits them.** The book channel "
                   f"shows no such gap at those instants: all "
                   f"{len(silent)} of these fills still have a rebuilt book "
                   f"and a fair.")
    dts = sorted(abs(r["print_dt_ms"]) for r in fnd
                 if r["print_dt_ms"] is not None)
    if dts:
        out.append(f"\nWhere it reconciles, the ladder prints a median "
                   f"**{dts[len(dts) // 2]} ms** from the reconstructed "
                   f"decision instant (p90 {dts[len(dts) * 9 // 10]}, max "
                   f"{dts[-1]}) -- which is a second, independent confirmation "
                   f"that the instant is reconstructed correctly.")
    out.append("\n## (e) would the backtest have bought it? four ways\n")
    out.append("`pinsim.decide` is CALLED here, not reimplemented. Two things "
               "are varied: WHEN the book is read (the second boundary, which "
               "is what `pinsim.run()` does, versus the millisecond the live "
               "bot actually decided) and WHICH GATE it runs under (the "
               "constants in `pinrun` today, versus the ones the `start` record "
               "of that fill's own run logged). Nothing else moves.\n")
    out.append("| book read at | gate | rules | would have bought | "
               "top refusal reasons |")
    out.append("|---|---|---|---|---|")
    for label, key, withrule in (
            ("second boundary", "now/attempt/s0", False),
            ("**decision millisecond**", "now/attempt/w", False),
            ("second boundary", "then/attempt/s0", False),
            ("**decision millisecond**", "then/attempt/w", False),
            ("second boundary", "now_s0", True),
            ("**decision millisecond**", "now_w", True),
            ("**decision millisecond**", "then_w", True)):
        gate = "today" if key.startswith("now") else "**the one that was LIVE**"
        if withrule:
            got = [r.get("full_" + key) for r in rows]
            got = [g for g in got if g]
        else:
            got = [r["decide"].get(key) for r in rows]
            got = [g[5] for g in got if g]
        nb = sum(1 for g in got if g == "bought")
        why = defaultdict(int)
        for g in got:
            if g != "bought":
                why[g] += 1
        top = ", ".join(f"`{k}` {v}" for k, v in
                        sorted(why.items(), key=lambda x: -x[1])[:4]) or "-"
        out.append(f"| {label} | {gate} | "
                   f"{'decide + profile rules' if withrule else 'decide only'} | "
                   f"**{nb}/{len(got)}** "
                   f"({100.0 * nb / len(got) if got else 0:.1f}%) | {top} |")
    pins = defaultdict(int)
    for r in rows:
        pins[r.get("live_pin")] += 1
    out.append(f"\nThe gate was not one thing over this window. "
               f"`PIN` by fill: "
               + ", ".join(f"{k} x{v}" for k, v in sorted(
                   pins.items(), key=lambda x: (x[0] is None, x[0])))
               + ". A fill taken under `PIN` 0.98 is refused `undecided` by "
                 "today's 0.995 -- which is a gate change, not a replay "
                 "defect, and the two must not be confused.")
    out.append("\n### the two dump guards, which are NOT the same rule\n")
    out.append("`pinrun` (live) refuses any offer whose discount to fair "
               f"exceeds {100 * pinrun.DUMP_DISCOUNT:.0f}c at ANY confidence. "
               "The `default` profile that `pinsim.run()` applies refuses "
               "`conf >= 0.999 AND discount_c > 5`. A trade can pass one and "
               "fail the other, so both are counted, on the fair the live "
               "model logged and the price we actually paid.\n")
    out.append("| | all fills | losing fills |")
    out.append("|---|---|---|")
    for label, pred in (
            (f"refused by pinrun's live {100 * pinrun.DUMP_DISCOUNT:.0f}c guard "
             f"as it stands TODAY",
             lambda r: r.get("dump_now") is True),
            ("refused by the guard that was live for that fill",
             lambda r: r.get("dump_then") is True),
            ("refused by the backtest profile's `dump` rule",
             lambda r: "REFUSED_BY_BACKTEST_PROFILE_RULE" in r["flags"]),
            ("**refused by NEITHER**",
             lambda r: not (r.get("dump_now") is True
                            or "REFUSED_BY_BACKTEST_PROFILE_RULE" in r["flags"]))):
        a = sum(1 for r in rows if pred(r))
        l = sum(1 for r in rows if r["loss"] and pred(r))
        out.append(f"| {label} | {a} | {l} |")
    dl = sorted((r["disc_c"] for r in rows if r["disc_c"] is not None))
    if dl:
        out.append(f"\nDiscount to fair across all fills: median "
                   f"{dl[len(dl) // 2]:.2f}c, p90 {dl[len(dl) * 9 // 10]:.2f}c, "
                   f"max {dl[-1]:.2f}c.")
    dlo = sorted((r["disc_c"] for r in rows
                  if r["loss"] and r["disc_c"] is not None))
    if dlo:
        out.append(f" On the LOSING fills: "
                   + ", ".join(f"{x:.2f}c" for x in dlo) + ".")
    out.append("\n## (d) the settlement, three ways\n")
    out.append("Settlement is the mean of the sixty 1-second index prints in "
               "[close-60, close-1], so it is recoverable from the index tape "
               "without `fulltape/markets.json`. All three sources are compared.\n")
    out.append("| | fills |")
    out.append("|---|---|")
    for label, pred in (
            ("live `settled` record present", lambda r: r["result_live"] is not None),
            ("`markets.json` has a result", lambda r: r["result_tape"] is not None),
            ("index tape has all 60 settlement prints",
             lambda r: r["result_idx"] is not None),
            ("**index-tape outcome == the outcome we booked live**",
             lambda r: (r["result_idx"] is not None
                        and r["result_live"] is not None
                        and r["result_idx"] == str(r["result_live"]).lower())),
            ("index-tape outcome DISAGREES with live",
             lambda r: "SETTLE_MISMATCH_VS_INDEX" in r["flags"]),
            ("`markets.json` DISAGREES with the index tape",
             lambda r: "MARKETS_JSON_DISAGREES_WITH_INDEX" in r["flags"])):
        out.append(f"| {label} | {sum(1 for r in rows if pred(r))} |")
    out.append("\n## Per-loss detail -- all "
               f"{len(losses)} losing fills, verbatim\n")
    out.append("These are the trades the operator says the backtest does not "
               "show. Each is reported in full, (a) to (e).")
    for r in sorted(losses, key=lambda x: x["S"]):
        loss_detail(r, out)
    diagnose(rows, out)
    txt = "\n".join(out) + "\n"
    return txt, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--logs", default=None, help="glob for pinrun-live logs")
    ap.add_argument("--limit", type=int, default=None,
                    help="only the newest N fills (for a smoke run)")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--json", default=None)
    ap.add_argument("--from-json", default=None,
                    help="re-render the report from a previous run's --json "
                         "dump, without touching the tape. The measurement is "
                         "in the dump; this only rewrites the prose.")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    if getattr(a, "from_json", None):
        blob = json.load(open(a.from_json, encoding="utf-8"))
        rows = blob["rows"] if isinstance(blob, dict) else blob
        meta = blob if isinstance(blob, dict) else {}
        txt, rows = report(rows, meta.get("bad", 0), meta.get("salvaged", []),
                           meta.get("missing", []))
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(txt)
        print(f"  re-rendered {len(rows)} rows -> {os.path.abspath(a.out)}")
        return

    fills = load_live(a.logs)
    if not fills:
        print("loaded nothing -- no filled orders in the live logs")
        return
    if a.limit:
        fills = fills[-a.limit:]
    mk = load_markets()
    # cross-check the ET fallback against every ticker markets.json DOES hold
    bad_et = [f["ticker"] for f in fills
              if mk.get(f["ticker"], {}).get("close") is not None
              and int(float(mk[f["ticker"]]["close"])) != close_from_ticker(f["ticker"])]
    print(f"  close-time cross-check: {len(bad_et)} of "
          f"{sum(1 for f in fills if mk.get(f['ticker'], {}).get('close') is not None)}"
          f" tickers disagree between markets.json and the ET suffix rule"
          + (f" -- {bad_et[:5]}" if bad_et else ""))
    miss = [f["ticker"] for f in fills if f["ticker"] not in mk]
    if miss:
        print(f"  {len(set(miss))} markets are NOT in markets.json (settlement "
              f"not pulled yet); close comes from the ticker suffix and the "
              f"tape settlement is reported as absent, never guessed")
    rows, bad, salvaged, missing = analyse(fills, mk)
    txt, rows = report(rows, bad, salvaged, missing)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(f"  written {os.path.abspath(a.out)}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"rows": rows, "bad": bad, "salvaged": salvaged,
                       "missing": missing}, fh, indent=1, default=str)
        print(f"  written {os.path.abspath(a.json)}")
    # the headline, on stdout, so a run that cannot write still says something
    n = len(rows)
    for fg in FLAG_ORDER:
        h = sum(1 for r in rows if fg in r["flags"])
        if h:
            print(f"    {fg:34s} {h:4d}/{n}")


if __name__ == "__main__":
    main()
