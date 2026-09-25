"""competitors.py -- who else trades the 15-minute crypto markets, and which of
them is on the other side of OUR losing fills.  Written 2026-09-25.

WHAT IT MEASURES (all from the recorder's `trade` channel, read-only, one
gzip hour at a time; the 12 up/down coin series only -- no oil, metals, race):

1. TAKER ORDERS. Kalshi prints one trade per resting order a taker hits, and
   every print of one taker order carries the same exchange millisecond and
   side. So prints are grouped by (ticker, ts_ms, taker_side) into taker
   orders. Each order gets a LANE from where and when it trades:

       dust                      under 1 contract
       final-seconds sniper      <=10 s left, paying >=90c
       late favourite buyer      10-60 s left, paying >=85c   (our lane)
       late longshot buyer       <=60 s left, paying <=15c
       late mid-price trader     <=60 s left, 15-85c
       early favourite buyer     >60 s left, >=85c
       early longshot buyer      >60 s left, <=15c
       early mid-price trader    >60 s left, 15-85c

   plus a SPEED tag: the order printed in the first 150 ms of a second, right
   after the settlement index's once-a-second print (uniform arrival puts 15
   of 100 there; a bot reacting to the index puts far more).

2. FIXED-SIZE BOTS. A taker that always sends the same odd size (13.37, 86,
   7.5 ...) leaves that exact total on every order it fills completely. An
   "odd" size is >=1 contract and not a round number (not a multiple of 5 and
   not 1-10). A size seen in >=20 distinct closes is a recurring actor; its
   profile (lane mix, time left, index-reaction share, how often its side
   won, money per contract after the taker fee) is printed.

3. MAKER PIECES. Inside one taker order, every print but the last used up a
   resting order completely, so its size is that maker's posted size. Odd
   sizes that recur across closes are resting-order bots; they are profiled
   the same way (money from the MAKER's side).

4. OUR FILLS. Every entry order of ours with a fill (results/pinrun-live-*.jsonl,
   `kind=order`, leg early/full/topup/late_add) is joined to the tape: the
   taker order on the same ticker and side printing within 2.5 s after our
   send whose total matches what we filled. From that we read the makers we
   hit (pieces) and every OTHER taker order within 3 s before (sellers of our
   side = takers buying the other side) and after. Win/loss is Kalshi's
   ledger (`kalshi_ledger.json` via pinday.ledger_markets), one row per
   market; a market is a loser when the ledger says it lost money.

5. TAPE-WIDE WARNING TEST (question 3 with more n). For every market, the
   first moment with 10-45 s left that a taker paid >=90c for one side (the
   favourite) is a "we could have bought here" moment. Was there a taker
   buying the OTHER side for >=25 contracts in the 5 s before it? How often
   did the favourite then lose, with vs without? This is what the MARKET did
   -- it is NOT our loss rate (CLAUDE.md 2026-09-10 amendment 5) and the
   report must never present it as one.

Outcomes come from the recorder's `market_lifecycle_v2` "determined" events.
Everything is clustered by close; n is markets or closes, never prints.

    python research/competitors.py --selftest
    python research/competitors.py --start 2026-09-18T07 --end 2026-09-25T07
"""
import argparse
import bisect
import calendar
import collections
import glob
import gzip
import json
import math
import os
import re
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
RESULTS = os.path.join(os.path.dirname(HERE), "results")

COINS = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
         "KXBNB15M", "KXADA15M", "KXBCH15M", "KXZEC15M", "KXHYPE15M",
         "KXNEAR15M", "KXTON15M")
COIN_SET = set(COINS)
ENTRY_LEGS = ("early", "full", "topup", "late_add")
FAST_MS = 150            # "right after the index print"
MIN_CLOSES = 20          # a recurring actor
BIG_AGAINST = 25.0       # contracts bought against the favourite
WARN_BIGS = (10.0, 25.0, 100.0)
MONTHS = {m: i + 1 for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT",
     "NOV", "DEC"))}
TICK_RE = re.compile(r"^(KX[A-Z]+15M)-(\d\d)([A-Z]{3})(\d\d)(\d\d)(\d\d)-")


# --------------------------------------------------------------- basics
def close_of_ticker(tk, et_hours=4):
    """UTC epoch of a 15-min ticker's close. The ticker is EASTERN time; the
    offset is 4 h (EDT) until 2026-11-01. None when it cannot be parsed."""
    m = TICK_RE.match(tk or "")
    if not m:
        return None
    _, yy, mon, dd, hh, mi = m.groups()
    if mon not in MONTHS:
        return None
    return calendar.timegm((2000 + int(yy), MONTHS[mon], int(dd), int(hh),
                            int(mi), 0)) + et_hours * 3600


def fee(px):
    return 0.07 * px * (1.0 - px)


def lane(tau, px, size):
    if size < 1.0:
        return "dust"
    if tau <= 60:
        if tau <= 10 and px >= 0.90:
            return "final-seconds sniper"
        if px >= 0.85:
            return "late favourite buyer"
        if px <= 0.15:
            return "late longshot buyer"
        return "late mid-price trader"
    if px >= 0.85:
        return "early favourite buyer"
    if px <= 0.15:
        return "early longshot buyer"
    return "early mid-price trader"


def size_key(x):
    return "%.2f" % x


def is_odd(x):
    """A size a person would not type: >=1 contract and not a whole number.
    (Whole numbers 11, 13, 17 ... turned up in ~600 of ~670 closes each on
    7 days -- that is everybody, not a bot, so they are not fingerprints.)"""
    if x < 1.0:
        return False
    return abs(x - round(x)) >= 1e-9


def parse_print(msg):
    """(ticker, ts_ms, side, px_taker, count) or None."""
    try:
        tk = msg["market_ticker"]
        side = msg["taker_side"]
        yp = float(msg["yes_price_dollars"])
        px = yp if side == "yes" else float(msg["no_price_dollars"])
        return tk, int(msg["ts_ms"]), side, px, float(msg["count_fp"])
    except (KeyError, TypeError, ValueError):
        return None


class Grouper:
    """Consecutive prints with the same (ticker, ts_ms, side) are one taker
    order. Different markets interleave, so the open group is kept per
    ticker. `emit(order)` gets dicts with pieces in print order."""

    def __init__(self, emit):
        self.emit = emit
        self.open = {}

    def add(self, p):
        tk, ts, side, px, cnt = p
        g = self.open.get(tk)
        if g is not None and g["ts"] == ts and g["side"] == side:
            g["pieces"].append((px, cnt))
            return
        if g is not None:
            self.emit(g)
        self.open[tk] = {"tk": tk, "ts": ts, "side": side, "pieces": [(px, cnt)]}

    def flush(self):
        for g in self.open.values():
            self.emit(g)
        self.open = {}


def summarise(g, close_s):
    size = sum(c for _, c in g["pieces"])
    cost = sum(p * c for p, c in g["pieces"])
    px = cost / size if size > 0 else g["pieces"][0][0]
    tau = close_s - g["ts"] / 1000.0
    return {"tk": g["tk"], "ts": g["ts"], "side": g["side"], "size": size,
            "px": px, "px_max": max(p for p, _ in g["pieces"]),
            "tau": tau, "ms": g["ts"] % 1000, "n": len(g["pieces"]),
            "pieces": g["pieces"], "close": close_s,
            "lane": lane(tau, px, size)}


# --------------------------------------------------------------- aggregates
def new_prof(cap=40):
    # closes are counted, not stored: orders arrive in time order, so a new
    # close value is a new close (a set per size key cost 450 MB on 7 days)
    return {"n": 0, "nc": 0, "last": None, "lanes": collections.Counter(),
            "fast": 0, "taus": [], "pxs": [], "won_n": 0, "known": 0,
            "pnl": 0.0, "contracts": 0.0, "cap": cap}


def prof_add(pr, o, won, maker=False, contracts=None, px=None):
    """won: did THIS order's side win (None unknown). maker=True books the
    money from the resting side (the opposite of the taker)."""
    pr["n"] += 1
    if o["close"] != pr["last"]:
        pr["nc"] += 1
        pr["last"] = o["close"]
    pr["lanes"][o["lane"]] += 1
    if o["ms"] < FAST_MS:
        pr["fast"] += 1
    if len(pr["taus"]) < pr["cap"]:
        pr["taus"].append(o["tau"])
        pr["pxs"].append(o["px"] if px is None else px)
    c = o["size"] if contracts is None else contracts
    p = o["px"] if px is None else px
    if won is not None:
        pr["known"] += 1
        pr["won_n"] += 1 if won else 0
        per = (1.0 - p) if won else -p
        per -= fee(p)
        if maker:
            per = -(per + fee(p))    # maker pays no fee, gets the other side
        pr["pnl"] += per * c
        pr["contracts"] += c


def median(xs):
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def prof_row(pr):
    return {"orders": pr["n"], "closes": pr["nc"],
            "top_lane": pr["lanes"].most_common(1)[0] if pr["lanes"] else None,
            "lane_share": (pr["lanes"].most_common(1)[0][1] / pr["n"]) if pr["n"] else 0,
            "fast_per100": 100.0 * pr["fast"] / pr["n"] if pr["n"] else 0,
            "tau_med": median(pr["taus"]), "px_med": median(pr["pxs"]),
            "won_per100": 100.0 * pr["won_n"] / pr["known"] if pr["known"] else None,
            "known": pr["known"],
            "c_per_contract": 100.0 * pr["pnl"] / pr["contracts"] if pr["contracts"] else None,
            "dollars": pr["pnl"]}


def recurring(profiles, min_closes=MIN_CLOSES, top=15, odd_only=True):
    rows = []
    for k, pr in profiles.items():
        if odd_only and not is_odd(float(k)):
            continue
        if pr["nc"] < min_closes:
            continue
        r = prof_row(pr)
        r["size"] = k
        rows.append(r)
    rows.sort(key=lambda r: -r["closes"])
    return rows[:top]


# --------------------------------------------------------------- warning test
def warning_test(orders_by_market, outcome, big=BIG_AGAINST, look_s=5.0,
                 lo=10.0, hi=45.0, fav_px=0.90):
    """orders_by_market: {tk: [(tau, side, px, size, lane, sizekey), ...]}.
    Returns {'with': [n_mk, fav_lost, closes], 'without': [...], rows}."""
    res = {"with": [0, 0, set()], "without": [0, 0, set()]}
    for tk, od in orders_by_market.items():
        won_yes = outcome.get(tk)
        if won_yes is None:
            continue
        od = sorted(od, key=lambda x: -x[0])          # time order: tau falls
        ent = None
        for o in od:
            if lo < o[0] <= hi and o[2] >= fav_px and o[3] >= 1.0:
                ent = o
                break
        if ent is None:
            continue
        fav = ent[1]
        against = sum(o[3] for o in od
                      if o[1] != fav and ent[0] < o[0] <= ent[0] + look_s)
        cell = "with" if against >= big else "without"
        fav_won = (won_yes == 1) == (fav == "yes")
        res[cell][0] += 1
        res[cell][1] += 0 if fav_won else 1
        res[cell][2].add(close_of_ticker(tk))
    return res


# --------------------------------------------------------------- our fills
def send_ms(r):
    """Send time in ms. Records before 2026-09-2x have no t_ms_send; their
    client_order_id is 'pin-<send ms>-<hex>', written at the same moment."""
    ts = r.get("t_ms_send")
    if ts:
        return int(ts)
    parts = str(r.get("client_order_id") or "").split("-")
    if len(parts) >= 2 and parts[1].isdigit() and len(parts[1]) == 13:
        return int(parts[1])
    return None


def want_of(r):
    """Our side. Older records lack `want`: exec_price equals exec_yes_price
    exactly when we bought YES (all our prices are >=85c, so never 50c)."""
    w = r.get("want")
    if w in ("yes", "no"):
        return w
    try:
        ep, ey = float(r.get("exec_price")), float(r.get("exec_yes_price"))
    except (TypeError, ValueError):
        return None
    if abs(ep - 0.5) < 1e-9:
        return None
    return "yes" if abs(ep - ey) < 1e-9 else "no"


def load_our_fills(paths, t0_ms, t1_ms):
    out = []
    for p in paths:
        try:
            fh = open(p, encoding="utf-8")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"kind": "order"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("leg") not in ENTRY_LEGS or not r.get("filled"):
                    continue
                ts, want = send_ms(r), want_of(r)
                if not ts or want is None or not (t0_ms <= ts < t1_ms):
                    continue
                out.append({"tk": r["ticker"], "want": want, "t": int(ts),
                            "filled": float(r["filled"]),
                            "px": r.get("exec_price") or r.get("limit_sent"),
                            "leg": r.get("leg"), "tau": r.get("tau_at_send"),
                            "sell_share_3s": r.get("sell_share_3s")})
    out.sort(key=lambda f: f["t"])
    return out


def join_fill(f, orders, window_ms=2500, ctx_ms=3000):
    """orders: taker orders (summarised) on f's ticker, any side, time-sorted.
    Returns the match and its context, or None."""
    best = None
    for o in orders:
        if o["side"] != f["want"] or not (f["t"] - 250 <= o["ts"] <= f["t"] + window_ms):
            continue
        d = abs(o["size"] - f["filled"])
        if best is None or (d, o["ts"]) < (best[0], best[1]["ts"]):
            best = (d, o)
    if best is None:
        return None
    d, me = best
    ts = me["ts"]
    before = [o for o in orders if o is not me and ts - ctx_ms <= o["ts"] < ts]
    after = [o for o in orders if o is not me and ts < o["ts"] <= ts + ctx_ms]
    sellers = [o for o in before if o["side"] != f["want"]]
    buyers = [o for o in before if o["side"] == f["want"]]
    tot = sum(o["size"] for o in before)
    return {"me": me, "exact": d <= 0.02, "diff": d, "lag_ms": ts - f["t"],
            "makers": len(me["pieces"]),
            "maker_sizes": [c for _, c in me["pieces"]],
            "sellers": sellers, "buyers": buyers, "after": after,
            "sell_c": sum(o["size"] for o in sellers),
            "sell_share": (sum(o["size"] for o in sellers) / tot) if tot > 0 else None,
            "racers_after": [o for o in after if o["side"] == f["want"]],
            "sellers_after": [o for o in after if o["side"] != f["want"]]}


# --------------------------------------------------------------- tape pass
def hours(start, end):
    t = calendar.timegm(time.strptime(start, "%Y-%m-%dT%H"))
    e = calendar.timegm(time.strptime(end, "%Y-%m-%dT%H"))
    while t < e:
        yield time.strftime("%Y%m%dT%H", time.gmtime(t))
        t += 3600


def stream(path):
    """Yield parsed JSON lines; a torn last block ends the file quietly and
    is counted by the caller via the returned flag in `stream.torn`."""
    stream.torn = False
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except (EOFError, zlib.error, OSError):
        stream.torn = True


def load_outcomes(data, start, end):
    """{ticker: 1 yes / 0 no} from market_lifecycle_v2 'determined'."""
    out = {}
    s = time.strftime("%Y-%m-%dT%H", time.gmtime(
        calendar.timegm(time.strptime(start, "%Y-%m-%dT%H"))))
    e = time.strftime("%Y-%m-%dT%H", time.gmtime(
        calendar.timegm(time.strptime(end, "%Y-%m-%dT%H")) + 2 * 3600))
    for h in hours(s, e):
        p = os.path.join(data, "market_lifecycle_v2", h + ".jsonl.gz")
        if not os.path.exists(p):
            continue
        for r in stream(p):
            m = r.get("msg") or {}
            if m.get("event_type") != "determined":
                continue
            tk = m.get("market_ticker", "")
            if tk.split("-")[0] not in COIN_SET:
                continue
            res = m.get("result")
            if res in ("yes", "no"):
                out[tk] = 1 if res == "yes" else 0
    return out


PROMOTE_AT = 5            # a size key gets a full profile from its 5th close


def promote(light, full, k, close_s):
    """Count closes cheaply; build the full profile once a key has been seen
    in PROMOTE_AT closes. Orders before that are counted in `nc` only."""
    e = light.get(k)
    if e is None:
        light[k] = [1, close_s]
        return None
    if e[1] != close_s:
        e[0] += 1
        e[1] = close_s
    if e[0] >= PROMOTE_AT:
        pr = new_prof()
        pr["nc"] = e[0] - 1
        full[k] = pr
        return pr
    return None


def ticker_of_line(line):
    i = line.find('"market_ticker":"')
    if i < 0:
        return None
    i += 17
    return line[i:line.find('"', i)]


def run_fills_only(data, start, end, fills):
    """Only the context around our own fills: lines for other tickers are
    skipped before JSON parsing, so the week reads in a few minutes."""
    need = collections.defaultdict(list)
    for f in fills:
        need[f["tk"]].append((f["t"] - 10000, f["t"] + 6000))
    ctx = collections.defaultdict(list)
    missing = []

    def emit(g):
        close_s = close_of_ticker(g["tk"])
        if close_s is None:
            return
        for lo, hi in need.get(g["tk"], ()):
            if lo <= g["ts"] <= hi:
                ctx[g["tk"]].append(summarise(g, close_s))
                break

    for h in hours(start, end):
        p = os.path.join(data, "trade", h + ".jsonl.gz")
        if not os.path.exists(p):
            missing.append(h)
            continue
        gr = Grouper(emit)
        seen = set()
        try:
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                for line in fh:
                    tk = ticker_of_line(line)
                    if tk not in need:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                    except (ValueError, KeyError):
                        continue
                    tid = hash(m.get("trade_id"))
                    if tid in seen:
                        continue
                    seen.add(tid)
                    pp = parse_print(m)
                    if pp is not None:
                        gr.add(pp)
        except (EOFError, zlib.error, OSError):
            pass
        gr.flush()
    for tk in ctx:
        ctx[tk].sort(key=lambda o: o["ts"])
    return ctx, missing


def run(data, start, end, fills, outcome, log=print):
    taker, maker = {}, {}                            # size key -> profile
    light_t, light_m = {}, {}                        # size key -> [closes, last]
    late_t, late_m, light_lt, light_lm = {}, {}, {}, {}
    warn = {b: {"with": [0, 0, set()], "without": [0, 0, set()]} for b in WARN_BIGS}
    lanes = collections.defaultdict(lambda: new_prof(3000))
    late_orders = collections.defaultdict(list)      # tk -> compact tuples
    need = collections.defaultdict(list)             # tk -> [(lo, hi)]
    for f in fills:
        need[f["tk"]].append((f["t"] - 10000, f["t"] + 6000))
    ctx = collections.defaultdict(list)              # tk -> summarised orders
    stats = {"files": 0, "missing": [], "torn": 0, "prints": 0, "orders": 0,
             "no_outcome_orders": 0, "dup": 0, "per_hour": {}, "pruned": 0}
    prev_seen = set()

    def emit(g):
        close_s = close_of_ticker(g["tk"])
        if close_s is None:
            return
        o = summarise(g, close_s)
        if o["tau"] < 0 or o["tau"] > 900:
            return
        stats["orders"] += 1
        won_yes = outcome.get(o["tk"])
        won = None if won_yes is None else ((won_yes == 1) == (o["side"] == "yes"))
        if won is None:
            stats["no_outcome_orders"] += 1
        prof_add(lanes[o["lane"]], o, won)
        if o["size"] >= 1.0:
            k = size_key(o["size"])
            pr = taker.get(k) or promote(light_t, taker, k, o["close"])
            if pr is not None:
                prof_add(pr, o, won)
        for px, c in o["pieces"][:-1]:               # fully used resting orders
            if c >= 1.0 and is_odd(c):
                k = size_key(c)
                pr = maker.get(k) or promote(light_m, maker, k, o["close"])
                if pr is not None:
                    prof_add(pr, o, won, maker=True, contracts=c, px=px)
        if o["tau"] <= 60 and o["size"] >= 1.0:
            k = size_key(o["size"])
            pr = late_t.get(k) or promote(light_lt, late_t, k, o["close"])
            if pr is not None:
                prof_add(pr, o, won)
            if o["px"] >= 0.85:                   # resting sellers of the favourite
                for px, c in o["pieces"][:-1]:
                    if c >= 1.0:
                        k = size_key(c)
                        pr = late_m.get(k) or promote(light_lm, late_m, k, o["close"])
                        if pr is not None:
                            prof_add(pr, o, won, maker=True, contracts=c, px=px)
        if o["tau"] <= 50 and o["size"] >= 1.0:
            late_orders[o["tk"]].append((o["tau"], o["side"], o["px"], o["size"]))
        for lo, hi in need.get(o["tk"], ()):
            if lo <= o["ts"] <= hi:
                ctx[o["tk"]].append(o)
                break

    for h in hours(start, end):
        p = os.path.join(data, "trade", h + ".jsonl.gz")
        if not os.path.exists(p):
            stats["missing"].append(h)
            continue
        stats["files"] += 1
        gr = Grouper(emit)
        seen, n0 = set(), stats["prints"]
        for r in stream(p):
            m = r.get("msg")
            if not m:
                continue
            tk = m.get("market_ticker", "")
            if tk[:tk.find("-")] not in COIN_SET:
                continue
            tid = hash(m.get("trade_id"))
            if tid in seen or tid in prev_seen:
                stats["dup"] += 1
                continue
            seen.add(tid)
            pp = parse_print(m)
            if pp is None:
                continue
            stats["prints"] += 1
            gr.add(pp)
        gr.flush()
        prev_seen = seen
        # memory: a size seen once and not again within 6 h, or <3 times in
        # 24 h, is dropped from the cheap counter (printed as pruned). A
        # recurring actor needs 20 closes in 7 days; one this sparse at the
        # start can be missed -- that is the price of staying under 200 MB.
        now_s = calendar.timegm(time.strptime(h, "%Y%m%dT%H")) + 3600
        for light in (light_t, light_m, light_lt, light_lm):
            drop = [k for k, e in light.items()
                    if (e[0] < 2 and e[1] < now_s - 6 * 3600) or (e[0] < 3 and e[1] < now_s - 24 * 3600)]
            for k in drop:
                del light[k]
            stats["pruned"] += len(drop)
        hour_end = calendar.timegm(time.strptime(h, "%Y%m%dT%H")) + 3600
        done = [tk for tk in late_orders if (close_of_ticker(tk) or 0) <= hour_end]
        batch = {tk: late_orders.pop(tk) for tk in done}
        for b in WARN_BIGS:
            w = warning_test(batch, outcome, big=b)
            for cell in ("with", "without"):
                warn[b][cell][0] += w[cell][0]
                warn[b][cell][1] += w[cell][1]
                warn[b][cell][2] |= w[cell][2]
        stats["per_hour"][h] = stats["prints"] - n0
        if stream.torn:
            stats["torn"] += 1
        log("  %s  prints so far %d  orders %d" % (h, stats["prints"], stats["orders"]))
    for tk in ctx:
        ctx[tk].sort(key=lambda o: o["ts"])
    for b in WARN_BIGS:
        w = warning_test(late_orders, outcome, big=b)
        for cell in ("with", "without"):
            warn[b][cell][0] += w[cell][0]
            warn[b][cell][1] += w[cell][1]
            warn[b][cell][2] |= w[cell][2]
    stats["light_taker_keys"] = len(light_t)
    stats["light_maker_keys"] = len(light_m)
    stats["late_t"], stats["late_m"] = late_t, late_m
    return taker, maker, lanes, warn, ctx, stats


# --------------------------------------------------------------- our-fill table
def fill_table(fills, ctx, ledger, outcome):
    """Per MARKET (first entry fill per market), joined to the tape."""
    first = {}
    for f in fills:
        first.setdefault(f["tk"], f)
    rows = []
    for tk, f in first.items():
        j = join_fill(f, ctx.get(tk, []))
        led = ledger.get(tk)
        res = outcome.get(tk)
        side_lost = None if res is None else ((res == 1) != (f["want"] == "yes"))
        rows.append({"f": f, "j": j, "dollars": None if led is None else led["dollars"],
                     "hedged": None if led is None else led["hedged"],
                     "side_lost": side_lost, "close": close_of_ticker(tk)})
    return rows


def touch_sell(j):
    """Contracts bought AGAINST us in the 3 s before our print at a price
    no more than 1c under the touch (the other side's ask = 1 - our price),
    and never under 0.5c. That is
    somebody selling our side at our price -- as opposed to a lottery buyer
    taking 0.1c tickets off deep resting bids, which says nothing."""
    thr = max(0.005, (1.0 - j["me"]["px"]) - 0.01)
    return sum(o["size"] for o in j["sellers"] if o["px"] >= thr)


def features(row):
    j = row["j"]
    if j is None:
        return None
    s = j["sellers"]
    touch = touch_sell(j)
    return {
        "touch_sell_25": touch >= 25.0,
        "touch_sell_100": touch >= 100.0,
        "lottery_only": bool(s) and touch < 1.0,
        "one_maker": j["makers"] == 1,
        "sellers_any": len(s) > 0,
        "sell_big": j["sell_c"] >= BIG_AGAINST,
        "seller_mid": any(o["lane"] in ("late mid-price trader",) for o in s),
        "seller_fast": any(o["ms"] < FAST_MS and o["size"] >= 1 for o in s),
        "seller_oddbot": any(is_odd(o["size"]) for o in s),
        "sell_share_gt_half": j["sell_share"] is not None and j["sell_share"] > 0.5,
        "racer_after": len(j["racers_after"]) > 0,
        "seller_after": sum(o["size"] for o in j["sellers_after"]) >= BIG_AGAINST,
        "we_fast": j["me"]["ms"] < FAST_MS,
    }


def feature_split(rows):
    """{feature: {'with': [markets, losers, $], 'without': [...]}}"""
    out = {}
    for r in rows:
        ft = features(r)
        if ft is None or r["dollars"] is None:
            continue
        lost = r["dollars"] < 0
        for k, v in ft.items():
            c = out.setdefault(k, {"with": [0, 0, 0.0, set()], "without": [0, 0, 0.0, set()]})
            cell = c["with" if v else "without"]
            cell[0] += 1
            cell[1] += 1 if lost else 0
            cell[2] += r["dollars"]
            cell[3].add(r["close"])
    return out


# --------------------------------------------------------------- selftest
def selftest():
    import random
    rng = random.Random(7)
    fails = []

    def ck(c, msg):
        if not c:
            fails.append(msg)
            print("FAIL", msg)

    # ticker clock
    ck(close_of_ticker("KXETH15M-26SEP242315-15") ==
       calendar.timegm((2026, 9, 25, 3, 15, 0)), "ET ticker -> UTC close")
    ck(close_of_ticker("KXWTI-bad") is None, "bad ticker -> None")
    # grouping with interleaved markets
    got = []
    g = Grouper(got.append)
    for p in [("A", 1000, "yes", 0.9, 5), ("B", 1000, "no", 0.2, 1),
              ("A", 1000, "yes", 0.91, 3), ("A", 1001, "yes", 0.91, 2),
              ("B", 1000, "no", 0.21, 4)]:
        g.add(p)
    g.flush()
    sz = sorted((x["tk"], x["ts"], sum(c for _, c in x["pieces"])) for x in got)
    ck(sz == [("A", 1000, 8), ("A", 1001, 2), ("B", 1000, 5)], "grouper %r" % sz)

    # world for fixed-size bot detection
    def world(plant):
        prof = collections.defaultdict(new_prof)
        base = 1790000000
        for c in range(200):
            close_s = base + 900 * c
            tk = "KXBTC15M-X%d" % c
            for _ in range(40):
                sz = rng.choice([1, 2, 5, 10, 20, 50, 100, rng.randint(1, 300) + 0.0,
                                 round(rng.uniform(0.5, 300), 2)])
                tau = rng.uniform(1, 900)
                px = rng.uniform(0.01, 0.99)
                ts = int((close_s - tau) * 1000)
                o = summarise({"tk": tk, "ts": ts, "side": "yes",
                               "pieces": [(px, sz)]}, close_s)
                prof_add(prof[size_key(o["size"])], o, rng.random() < px)
            if plant and c % 2 == 0:
                ts = int((close_s - 40) * 1000) // 1000 * 1000 + 30
                o = summarise({"tk": tk, "ts": ts, "side": "no",
                               "pieces": [(0.97, 13.37)]}, close_s)
                prof_add(prof[size_key(13.37)], o, rng.random() < 0.97)
        return recurring(prof, min_closes=20)
    rows = world(True)
    ck(rows and rows[0]["size"] == "13.37", "planted bot is top recurring odd size")
    if rows:
        r = rows[0]
        ck(r["fast_per100"] > 90 and abs(r["tau_med"] - 40) < 1.5 and
           r["top_lane"][0] == "late favourite buyer", "planted bot profile %r" % r)
    nul = world(False)
    ck(not any(x["size"] == "13.37" for x in nul), "null world: no 13.37 bot")
    ck(all(x["fast_per100"] < 40 for x in nul), "null world: no fast bot")

    # maker money sign: a maker selling 97c that loses 97c when the taker wins
    pr = new_prof()
    o = summarise({"tk": "T", "ts": 0, "side": "yes", "pieces": [(0.97, 10)]}, 30)
    prof_add(pr, o, True, maker=True, contracts=10, px=0.97)
    ck(abs(pr["pnl"] - (-0.03 * 10)) < 1e-9, "maker loses 3c/contract when taker wins at 97c: %r" % pr["pnl"])
    pr = new_prof()
    prof_add(pr, o, False, maker=True, contracts=10, px=0.97)
    ck(abs(pr["pnl"] - 9.7) < 1e-9, "maker wins 97c when taker loses")

    # warning test: planted informed against-buyer
    def wworld(plant):
        obm, outc = {}, {}
        for i in range(3000):
            tk = "KXBTC15M-26SEP%02d%02d%02d-00" % (1 + i % 28, (i // 28) % 24, 15 * ((i // 700) % 4))
            tk = tk + str(i)
            fav = "yes" if i % 2 else "no"
            other = "no" if fav == "yes" else "yes"
            od = [(30.0, fav, 0.93, 10.0)]
            informed = plant and i % 5 == 0
            if informed or (not plant and i % 5 == 0):
                od.append((33.0, other, 0.07, 60.0))
            fav_wins = rng.random() < (0.5 if informed else 0.95)
            outc[tk] = 1 if (fav_wins == (fav == "yes")) else 0
            obm[tk] = od
        return warning_test(obm, outc)
    w = wworld(True)
    lw = w["with"][1] / max(1, w["with"][0])
    lo = w["without"][1] / max(1, w["without"][0])
    ck(lw > 0.4 and lo < 0.08, "warning test finds planted informed buyer %.2f vs %.2f" % (lw, lo))
    w = wworld(False)
    lw = w["with"][1] / max(1, w["with"][0])
    lo = w["without"][1] / max(1, w["without"][0])
    ck(abs(lw - lo) < 0.03, "warning test null: %.3f vs %.3f" % (lw, lo))

    # fill join
    close_s = 1790000900
    mk = lambda ts, side, pieces: summarise({"tk": "T", "ts": ts, "side": side, "pieces": pieces}, close_s)
    orders = [mk(1789999000 * 1000 + 870000 - 2000, "yes", [(0.08, 40)]),   # seller of our NO side
              mk(1789999000 * 1000 + 870000 - 1000, "no", [(0.95, 3)]),
              mk(1789999000 * 1000 + 870000 + 90, "yes", [(0.02, 86)]),    # decoy: wrong side same time
              mk(1789999000 * 1000 + 870000 + 95, "no", [(0.98, 1.0), (0.98, 85.0)]),
              mk(1789999000 * 1000 + 870000 + 1500, "no", [(0.99, 7)])]
    f = {"tk": "T", "want": "no", "t": 1789999000 * 1000 + 870000, "filled": 86.0}
    j = join_fill(f, orders)
    ck(j is not None and j["exact"] and j["makers"] == 2 and j["lag_ms"] == 95,
       "fill join exact match %r" % ((None if j is None else (j["exact"], j["makers"], j["lag_ms"])),))
    # the wrong-side order 5 ms before ours is not OUR fill but IS a seller
    ck(j is not None and abs(j["sell_c"] - 126) < 1e-9 and len(j["racers_after"]) == 1,
       "fill join context %r" % ((None if j is None else (j["sell_c"], len(j["racers_after"]))),))
    ck(j is not None and abs(j["sell_share"] - 126 / 129) < 1e-9, "sell share")
    j2 = join_fill(f, orders + [mk(1789999000 * 1000 + 870000 - 500, "yes", [(0.001, 900)])])
    ck(j2 is not None and abs(touch_sell(j2) - 126) < 1e-9 and abs(j2["sell_c"] - 1026) < 1e-9,
       "touch seller excludes the 0.1c lottery %r" % ((None if j2 is None else touch_sell(j2)),))
    # promotion: counted closes are exact, the profile starts at the 5th close
    lt, fu = {}, {}
    for c in (1, 1, 2, 3):
        promote(lt, fu, "13.37", c)
    ck("13.37" not in fu, "3 closes: not promoted")
    pr = None
    for c in (4, 5):
        pr = fu.get("13.37") or promote(lt, fu, "13.37", c)
        if pr is not None:
            prof_add(pr, {"close": c, "tk": "T", "lane": "x", "ms": 500, "tau": 1, "px": 0.5,
                          "size": 1}, None)
    ck("13.37" in fu and fu["13.37"]["nc"] == 5, "promoted at 5 closes, nc=%r" % (
        fu.get("13.37", {}).get("nc"),))
    # is_odd
    ck(is_odd(13.37) and not is_odd(86) and not is_odd(100) and not is_odd(0.5),
       "odd-size rule")
    # older log records: send ms from client_order_id, side from prices
    ck(send_ms({"client_order_id": "pin-1790306077347-61e3d1"}) == 1790306077347, "send ms fallback")
    ck(want_of({"exec_price": 0.97, "exec_yes_price": 0.03}) == "no" and
       want_of({"exec_price": 0.97, "exec_yes_price": 0.97}) == "yes", "want fallback")
    print("SELFTEST", "FAIL" if fails else "PASS", "(%d checks failed)" % len(fails))
    return not fails


# --------------------------------------------------------------- main
def pct(a, b):
    return "%.1f" % (100.0 * a / b) if b else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data", default=r"C:\kals\kalshi_data")
    ap.add_argument("--start", default="2026-09-18T07")
    ap.add_argument("--end", default="2026-09-25T07")
    ap.add_argument("--json", default=None, help="write the summary JSON here")
    ap.add_argument("--fills-only", action="store_true",
                    help="only our fills against the tape (skips the whole-tape profiles)")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        print("self-test failed; refusing to touch real data")
        sys.exit(1)
    t0 = calendar.timegm(time.strptime(a.start, "%Y-%m-%dT%H")) * 1000
    t1 = calendar.timegm(time.strptime(a.end, "%Y-%m-%dT%H")) * 1000
    fills = load_our_fills(sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl"))), t0, t1)
    print("our entry fills in window: %d orders, %d markets" % (len(fills), len({f['tk'] for f in fills})))
    outcome = load_outcomes(a.data, a.start, a.end)
    print("outcomes (lifecycle determined): %d markets" % len(outcome))
    import pinday
    led, why = pinday.load_ledger(os.path.join(RESULTS, "kalshi_ledger.json"))
    ledger = {}
    if led is None:
        print("NO LEDGER:", why)
    else:
        ledger, skipped = pinday.ledger_markets(led["rows"])
        print("ledger markets %d (skipped %d), written %s" % (len(ledger), skipped, led["written"]))
    if a.fills_only:
        ctx, missing = run_fills_only(a.data, a.start, a.end, fills)
        print("fills-only: trade hours missing %d" % len(missing))
        report_fills(fills, ctx, ledger, outcome, {})
        print("\nDONE")
        return
    taker, maker, lanes, warn, ctx, st = run(a.data, a.start, a.end, fills, outcome,
                                                    log=lambda s: None)
    print("trade files read %d, missing %d %s, torn %d, prints %d, taker orders %d, "
          "orders without outcome %d, duplicate prints dropped %d" % (
              st["files"], len(st["missing"]), st["missing"][:6], st["torn"], st["prints"],
              st["orders"], st["no_outcome_orders"], st["dup"]))
    ph = st["per_hour"]
    if ph:
        medp = median(list(ph.values()))
        thin = [h for h, v in sorted(ph.items()) if v < 0.3 * medp]
        print("prints per hour median %d; hours under 30%% of that (%d): %s" % (medp, len(thin), thin))
    out = {"stats": {k: v for k, v in st.items()}, "lanes": {}, "taker_bots": [],
           "maker_bots": [], "round_takers": []}
    print("\n== LANES (all taker orders) ==")
    for k, pr in sorted(lanes.items(), key=lambda kv: -kv[1]["n"]):
        r = prof_row(pr)
        out["lanes"][k] = r
        print("%-24s orders %8d closes %4d  fast/100 %5.1f  tau_med %6.1f px_med %.3f "
              "won/100 %s  c/contract %s  $ %10.2f  contracts %.0f" % (
                  k, r["orders"], r["closes"], r["fast_per100"], r["tau_med"] or -1,
                  r["px_med"] or -1, "-" if r["won_per100"] is None else "%.1f" % r["won_per100"],
                  "-" if r["c_per_contract"] is None else "%.2f" % r["c_per_contract"],
                  r["dollars"], pr["contracts"]))
    ours = collections.Counter(size_key(f["filled"]) for f in fills)
    print("\n== RECURRING ODD-SIZE TAKERS (>= %d closes) ==" % MIN_CLOSES)
    for r in recurring(taker, top=25):
        r["ours_n"] = ours.get(r["size"], 0)
        out["taker_bots"].append({k: (list(v) if isinstance(v, tuple) else v) for k, v in r.items()})
        print("size %-9s closes %4d orders %5d ours %3d  lane %-22s %3.0f/100  fast/100 %5.1f "
              "tau_med %6.1f px_med %.3f won/100 %s c/contract %s $ %.2f" % (
                  r["size"], r["closes"], r["orders"], r["ours_n"], r["top_lane"][0],
                  100 * r["lane_share"], r["fast_per100"], r["tau_med"], r["px_med"],
                  "-" if r["won_per100"] is None else "%.1f" % r["won_per100"],
                  "-" if r["c_per_contract"] is None else "%.2f" % r["c_per_contract"],
                  r["dollars"]))
    for title, dct, mk in (("LATE (<=60 s left) TAKER SIZES, whole numbers included", st.pop("late_t"), False),
                           ("LATE RESTING SELLERS OF THE FAVOURITE (>=85c, <=60 s), by resting size", st.pop("late_m"), True)):
        print("\n== %s (top 20 by closes) ==" % title)
        rows_l = recurring(dct, min_closes=MIN_CLOSES, top=20, odd_only=False)
        out.setdefault("late", {})[title] = rows_l
        for r in rows_l:
            print("size %-9s closes %4d orders %6d ours %3d lane %-22s %3.0f/100 fast/100 %5.1f tau_med %5.1f "
                  "px_med %.3f won/100 %s %s c/contract %s $ %.2f" % (
                      r["size"], r["closes"], r["orders"], ours.get(r["size"], 0), r["top_lane"][0],
                      100 * r["lane_share"], r["fast_per100"], r["tau_med"], r["px_med"],
                      "-" if r["won_per100"] is None else "%.1f" % r["won_per100"],
                      "maker" if mk else "taker",
                      "-" if r["c_per_contract"] is None else "%.2f" % r["c_per_contract"], r["dollars"]))
    print("\n== RECURRING ROUND-SIZE TAKERS (top 12 by closes) ==")
    rr = []
    for k, pr in taker.items():
        if is_odd(float(k)) or float(k) < 1 or pr["nc"] < MIN_CLOSES:
            continue
        r = prof_row(pr)
        r["size"] = k
        rr.append(r)
    rr.sort(key=lambda r: -r["closes"])
    for r in rr[:12]:
        out["round_takers"].append({k: (list(v) if isinstance(v, tuple) else v) for k, v in r.items()})
        print("size %-9s closes %4d orders %6d lane %-22s %3.0f/100 fast/100 %5.1f tau_med %6.1f "
              "px_med %.3f won/100 %s c/contract %s $ %.2f" % (
                  r["size"], r["closes"], r["orders"], r["top_lane"][0], 100 * r["lane_share"],
                  r["fast_per100"], r["tau_med"], r["px_med"],
                  "-" if r["won_per100"] is None else "%.1f" % r["won_per100"],
                  "-" if r["c_per_contract"] is None else "%.2f" % r["c_per_contract"], r["dollars"]))
    print("\n== RECURRING ODD-SIZE MAKER ORDERS (fully used resting orders, >= %d closes) ==" % MIN_CLOSES)
    for r in recurring(maker, top=20):
        out["maker_bots"].append({k: (list(v) if isinstance(v, tuple) else v) for k, v in r.items()})
        print("size %-9s closes %4d hits %5d  hit in lane %-22s %3.0f/100 fast/100 %5.1f "
              "tau_med %6.1f px_med %.3f  maker c/contract %s $ %.2f" % (
                  r["size"], r["closes"], r["orders"], r["top_lane"][0], 100 * r["lane_share"],
                  r["fast_per100"], r["tau_med"], r["px_med"],
                  "-" if r["c_per_contract"] is None else "%.2f" % r["c_per_contract"], r["dollars"]))
    # warning test
    print("\n== TAPE-WIDE: favourite at >=90c with 10-45 s left; someone bought the OTHER side "
          ">= %d contracts in the 5 s before ==" % BIG_AGAINST)
    for big in WARN_BIGS:
        w = warn[big]
        print("  against >= %5.0f: WITH  %5d markets %4d closes, favourite lost %4d (%s per 100) | "
              "WITHOUT %5d markets %4d closes, lost %4d (%s per 100)" % (
                  big, w["with"][0], len(w["with"][2]), w["with"][1], pct(w["with"][1], w["with"][0]),
                  w["without"][0], len(w["without"][2]), w["without"][1],
                  pct(w["without"][1], w["without"][0])))
        out.setdefault("warning", {})[str(big)] = {
            "with": [w["with"][0], w["with"][1], len(w["with"][2])],
            "without": [w["without"][0], w["without"][1], len(w["without"][2])]}
    report_fills(fills, ctx, ledger, outcome, out)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, default=str, indent=1)
    print("\nDONE")


def report_fills(fills, ctx, ledger, outcome, out):
    rows = fill_table(fills, ctx, ledger, outcome)
    joined = [r for r in rows if r["j"] is not None]
    exact = [r for r in joined if r["j"]["exact"]]
    print("\n== OUR FILLS joined to the tape: %d markets, joined %d, exact size match %d, "
          "no ledger row %d ==" % (len(rows), len(joined), len(exact),
                                   sum(1 for r in rows if r["dollars"] is None)))
    lags = sorted(r["j"]["lag_ms"] for r in joined)
    if lags:
        print("  print lag after our send, ms: median %d, p10 %d, p90 %d" % (
            lags[len(lags) // 2], lags[len(lags) // 10], lags[9 * len(lags) // 10]))
    losers = [r for r in joined if r["dollars"] is not None and r["dollars"] < 0]
    winners = [r for r in joined if r["dollars"] is not None and r["dollars"] >= 0]
    print("  losers %d (%s $) winners %d (%s $)" % (
        len(losers), "%.2f" % sum(r["dollars"] for r in losers), len(winners),
        "%.2f" % sum(r["dollars"] for r in winners)))
    for name, grp in (("LOSERS", losers), ("WINNERS", winners)):
        if not grp:
            continue
        mk = [r["j"]["makers"] for r in grp]
        print("  %s: makers hit median %s, one maker %s/100, sellers in 3 s before %s/100, "
              "sold >=%d %s/100, fast seller %s/100, odd-size seller %s/100, racer after %s/100" % (
                  name, median(mk), pct(sum(1 for m in mk if m == 1), len(grp)),
                  pct(sum(1 for r in grp if r["j"]["sellers"]), len(grp)), BIG_AGAINST,
                  pct(sum(1 for r in grp if r["j"]["sell_c"] >= BIG_AGAINST), len(grp)),
                  pct(sum(1 for r in grp if features(r)["seller_fast"]), len(grp)),
                  pct(sum(1 for r in grp if features(r)["seller_oddbot"]), len(grp)),
                  pct(sum(1 for r in grp if r["j"]["racers_after"]), len(grp))))
        sl = collections.Counter(o["lane"] for r in grp for o in r["j"]["sellers"] if o["size"] >= 1)
        print("     lanes of the sellers (orders >=1 contract): %s" % dict(sl.most_common(6)))
    print("\n  feature split (per market, ledger money):")
    fs = feature_split(joined)
    out["features"] = {}
    for k, c in fs.items():
        w, wo = c["with"], c["without"]
        out["features"][k] = {"with": [w[0], w[1], round(w[2], 2), len(w[3])],
                              "without": [wo[0], wo[1], round(wo[2], 2), len(wo[3])]}
        print("   %-20s WITH %4d mk %3d cl lost %3d (%s/100) $%9.2f | WITHOUT %4d mk lost %3d (%s/100) $%9.2f" % (
            k, w[0], len(w[3]), w[1], pct(w[1], w[0]), w[2], wo[0], wo[1], pct(wo[1], wo[0]), wo[2]))
    print("\n  every LOSER, one line each:")
    out["losers"] = []
    for r in sorted(losers, key=lambda r: r["f"]["t"]):
        j = r["j"]
        f = r["f"]
        sel = sorted(((round(o["size"], 2), round(o["px"], 3), round((j["me"]["ts"] - o["ts"]) / 1000.0, 2), o["lane"])
                      for o in j["sellers"] if o["size"] >= 1), key=lambda x: -x[0])[:4]
        line = {"tk": f["tk"], "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(f["t"] / 1000)),
                "want": f["want"], "tau": f["tau"], "px": f["px"], "filled": f["filled"],
                "dollars": round(r["dollars"], 2), "hedged": r["hedged"], "makers": j["makers"],
                "maker_sizes": [round(x, 2) for x in j["maker_sizes"]][:6], "sell_c": round(j["sell_c"], 2),
                "touch_sell_c": round(touch_sell(j), 2),
                "sellers_top": sel, "racers_after": len(j["racers_after"]),
                "sold_after": round(sum(o["size"] for o in j["sellers_after"]), 2)}
        out["losers"].append(line)
        print("   ", json.dumps(line))
    unj = [r for r in rows if r["j"] is None]
    print("\n  not joined (no print on our side within 2.5 s): %d markets; losers among them %d" % (
        len(unj), sum(1 for r in unj if r["dollars"] is not None and r["dollars"] < 0)))
    for r in unj:
        if r["dollars"] is not None and r["dollars"] < 0:
            print("    unjoined loser %s %s $%.2f" % (r["f"]["tk"], time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(r["f"]["t"] / 1000)), r["dollars"]))
    print("\n  by ET-free UTC day, markets / losers / $ (joined):")
    byday = collections.defaultdict(lambda: [0, 0, 0.0])
    for r in joined:
        if r["dollars"] is None:
            continue
        d = time.strftime("%Y-%m-%d", time.gmtime(r["f"]["t"] / 1000))
        byday[d][0] += 1
        byday[d][1] += 1 if r["dollars"] < 0 else 0
        byday[d][2] += r["dollars"]
    for d in sorted(byday):
        print("    %s %4d %3d %9.2f" % (d, *byday[d]))


if __name__ == "__main__":
    main()
