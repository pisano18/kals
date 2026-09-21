#!/usr/bin/env python3
"""racebook.py -- the Coin Race basket constraint, measured on the live book.

THE IDEA, and why it is different from everything else tried on this product.

A Coin Race has five legs and EXACTLY ONE of them settles YES. So a basket of
one YES contract on every leg is worth exactly $1.00 at settlement, whatever
the coins do, whoever wins, however the race turns. Two consequences that owe
nothing to any forecast:

    sum of the five YES ASKS  <  $1.00 - fees   ->  buy all five, riskless
    sum of the five YES BIDS  >  $1.00 + fees   ->  sell all five, riskless

No model. No index. No view on which coin wins. The forecast this project has
spent weeks on is not an input, and the adverse-selection trap that makes our
live loss rate 31x the tape's cannot apply: there is no loss state. If leg 3
is sold to us because the seller knows leg 3 is dead, we still collect exactly
$1.00 for the basket.

EVERY OTHER COIN RACE STRATEGY HERE PRICES A WINNER. This one prices the
ARITHMETIC, and the arithmetic is not an opinion.

WHAT COULD STILL GO WRONG -- measured here, not assumed:

  1. IT MAY SIMPLY NOT HAPPEN. Measured below: how often, at what size.
  2. LEGGING RISK. Five orders cannot be sent in the same instant. So the file
     reports how LONG each opportunity persists, because an edge that lives
     one second is not tradeable and one that lives thirty is.
  3. STALE QUOTES. A leg nobody has updated for five minutes is not an offer.
     Every quote carries its age and the scan is run at several age caps.
  4. PHANTOM SIZE. `yes_ask_size_fp` at the top of book is what the exchange
     advertises, not what we would fill. The dollars here are a CEILING and
     are labelled as one everywhere they appear.
  5. FEES. Takers pay 0.07*p*(1-p) per contract, rounded up per order. Charged
     on all five legs, at the real contract count, never omitted.

INSTRUMENT: the `ticker` channel -- top of book with sizes, the exchange's own
unified best (a YES ask includes the synthetic from resting NO bids). Not the
replay, not pinsim, not a decision reproduction. Per the standing rule the
ordering is index > tape > our fills > replay; this is the tape.

    python research/racebook.py --selftest
    python research/racebook.py                 # scan everything on disk
    python research/racebook.py --hours 48
"""
import argparse
import collections
import glob
import gzip
import json
import math
import os
import shutil
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

COINS = ("BTC", "ETH", "SOL", "XRP", "HYPE")
SERIES = "KXCRYPTOLEAD15M"
WINDOW = 900
DATA = r"C:\kals\kalshi_data"
CACHE = os.path.join(REPO, "flow_cache", "racebook")

# A basket is only interesting if we could put real money through it.
SIZES = (1, 5, 10, 25, 50)
AGES = (5, 15, 30, 120)
DEFAULT_AGE = 30


# ------------------------------------------------------------------ fees
def order_fee(n, p):
    """Kalshi taker fee in DOLLARS for `n` contracts at price `p` (dollars).

    0.07 * n * p * (1-p), rounded UP to the next whole cent per order. Rounded
    up, so a five-leg basket pays five roundings -- which is exactly why this
    is charged per leg here and never as one blended number."""
    if n <= 0:
        return 0.0
    return math.ceil(0.07 * n * p * (1.0 - p) * 100.0 - 1e-9) / 100.0


def basket_buy_profit(asks, n):
    """Dollars of profit from buying `n` of every leg at `asks`, after fees.

    Payout is exactly $1.00 per basket because exactly one leg settles YES."""
    cost = n * sum(asks)
    fees = sum(order_fee(n, a) for a in asks)
    return n * 1.00 - cost - fees


def basket_sell_profit(bids, n):
    """Dollars from selling `n` of every leg at `bids` (equivalently buying NO
    on all five), after fees. We receive sum(bids) and pay out exactly $1.00."""
    if n <= 0:
        return 0.0
    got = n * sum(bids)
    fees = sum(order_fee(n, b) for b in bids)
    return got - n * 1.00 - fees


# --------------------------------------------------------------- extraction
def _grab(line, name):
    """The value of `"name"` in a JSON line, as a string, or None.

    Tolerant of whitespace after the colon and of the value being quoted or
    bare, because a serialiser change that silently stopped matching is
    exactly how 68,976,084 orderbook deltas once went unparsed here while
    every stage still exited 0. The scan shouts if the parse rate collapses;
    this makes that shout unlikely to be needed."""
    i = line.find('"' + name + '"')
    if i < 0:
        return None
    i = line.find(":", i + len(name) + 2)
    if i < 0:
        return None
    i += 1
    while i < len(line) and line[i] in " \t":
        i += 1
    if i >= len(line):
        return None
    if line[i] == '"':
        j = line.find('"', i + 1)
        return line[i + 1:j] if j > i else None
    j = i
    while j < len(line) and line[j] not in ",}] \t\n":
        j += 1
    return line[i:j] or None


def _fields(line):
    """Pull the six fields we need out of one ticker line without json.loads.

    The ticker channel is 45k lines an hour and most of it is not this series;
    a substring gate plus a hand parse is ~20x faster than decoding. Returns
    None on anything that does not look like a complete CRYPTOLEAD ticker.

    UNITS ARE NEVER INFERRED FROM MAGNITUDE (hard rule 5). The `_dollars`
    fields are read as dollars because of their NAME, and a line that does not
    carry those names is skipped rather than guessed at."""
    tick = _grab(line, "market_ticker")
    if not tick or not tick.startswith(SERIES + "-"):
        return None
    rest = tick[len(SERIES) + 1:]
    stamp, _, coin = rest.rpartition("-")
    if coin not in COINS or not stamp:
        return None
    try:
        bid = float(_grab(line, "yes_bid_dollars"))
        ask = float(_grab(line, "yes_ask_dollars"))
        bsz = float(_grab(line, "yes_bid_size_fp"))
        asz = float(_grab(line, "yes_ask_size_fp"))
        rx_ms = int(_grab(line, "_rx_ms"))
    except (TypeError, ValueError):
        return None
    return (rx_ms, stamp, coin, bid, ask, bsz, asz)


# One line copied verbatim off the tape (ticker/20260921T05.jsonl.gz). A
# fixture the collector actually wrote beats any fixture this file invents:
# it is the only test that would fail if the wire format moved.
REAL_LINE = (
    '{"type":"ticker","sid":6,"msg":{"market_id":"4ac7cb26-aacc-420e-860e-'
    '5e7f054d8aa8","market_ticker":"KXCRYPTOLEAD15M-26SEP210100-XRP",'
    '"price_dollars":"0.0100","yes_bid_dollars":"0.0000","yes_ask_dollars":'
    '"0.0100","volume_fp":"759.86","open_interest_fp":"666.18",'
    '"dollar_volume":379,"dollar_open_interest":333,"yes_bid_size_fp":"0.00",'
    '"yes_ask_size_fp":"78.00","last_trade_size_fp":"0.09","ts":1789966800,'
    '"ts_ms":1789966800000,"time":"2026-09-21T05:00:00Z"},'
    '"_rx_ms":1789966800649}')


def extract_hour(path, stats=None):
    """[(rx_ms, stamp, coin, bid, ask, bsz, asz)] for one source hour file.

    `stats` (a 2-list) counts candidate lines and parsed lines, so the caller
    can refuse to report on a file whose format it no longer understands."""
    rows = []
    try:
        with gzip.open(path, "rt") as fh:
            for line in fh:
                if "CRYPTOLEAD" not in line or '"ticker"' not in line:
                    continue
                if stats is not None:
                    stats[0] += 1
                r = _fields(line)
                if r is not None:
                    rows.append(r)
                    if stats is not None:
                        stats[1] += 1
    except (EOFError, zlib.error, OSError):
        pass                       # truncated tail: keep what parsed
    return rows


def parse_rate(files, n=3):
    """(candidates, parsed) over `n` uncached source files -- a live check that
    the wire format still matches the parser. A silent zero here is the bug
    class that let 68,976,084 deltas go unread while every stage exited 0."""
    stats = [0, 0]
    for fp in files[-n:]:
        extract_hour(fp, stats=stats)
    return tuple(stats)


def cached_hour(path, cache_dir=CACHE):
    """extract_hour with a gzipped CSV cache keyed on the source filename.

    The cache is written atomically -- a half-written cache read back on the
    next run would silently drop half a day."""
    if cache_dir is None:
        return extract_hour(path)
    os.makedirs(cache_dir, exist_ok=True)
    cp = os.path.join(cache_dir, os.path.basename(path).replace(".jsonl.gz", ".csv.gz"))
    if os.path.exists(cp):
        out = []
        try:
            with gzip.open(cp, "rt") as fh:
                for line in fh:
                    a = line.rstrip("\n").split(",")
                    if len(a) != 7:
                        continue
                    out.append((int(a[0]), a[1], a[2], float(a[3]), float(a[4]),
                                float(a[5]), float(a[6])))
            return out
        except (EOFError, zlib.error, OSError, ValueError):
            pass                   # corrupt cache: fall through and rebuild
    rows = extract_hour(path)
    fd, tmp = tempfile.mkstemp(dir=cache_dir, suffix=".tmp")
    os.close(fd)
    with gzip.open(tmp, "wt") as fh:
        for r in rows:
            fh.write("%d,%s,%s,%g,%g,%g,%g\n" % r)
    shutil.move(tmp, cp)
    return rows


def close_of(stamp):
    """26SEP210100 -> epoch seconds of the CLOSE.

    The stamp block is EASTERN -- pinracemodel proved this by reproducing 761
    of 761 winners with it. Reading it as UTC puts every race four hours from
    its own close."""
    import datetime as dt
    try:
        day = dt.datetime.strptime(stamp[:7], "%y%b%d")
        hh, mi = int(stamp[7:9]), int(stamp[9:11])
        return int((day.replace(hour=hh, minute=mi)
                    - dt.datetime(1970, 1, 1)).total_seconds()) + 4 * 3600
    except (ValueError, IndexError):
        return None


# ------------------------------------------------------------------- scan
class Leg:
    """Last known top of book for one leg, with the age of that knowledge."""
    __slots__ = ("bid", "ask", "bsz", "asz", "at")

    def __init__(self):
        self.bid = self.ask = self.bsz = self.asz = 0.0
        self.at = None

    def has_offer(self):
        """An offer exists only if something is actually resting there.

        A market with nothing on the yes-ask prints ask 1.0000 with size 0.
        Reading that as 'a dollar offer' would manufacture a basket out of a
        market with no sellers at all."""
        return self.at is not None and self.asz > 0 and 0.0 < self.ask < 1.0

    def has_bid(self):
        return self.at is not None and self.bsz > 0 and 0.0 < self.bid < 1.0


def scan_race(rows, close, tau_lo=1, tau_hi=900, max_age=DEFAULT_AGE):
    """One race. Returns a list of per-second states inside the tau band.

    Each state is (tau, side_state) where side_state carries the five legs'
    top of book as of that second, carried forward from the last message and
    refused once it is older than `max_age`.

    Rows must be this race's only. Anything at or after the close second is
    dropped: the book after a close is a settlement artefact, not a quote."""
    legs = {c: Leg() for c in COINS}
    rows = sorted(rows)
    out = []
    i = 0
    lo_sec = close - tau_hi
    hi_sec = close - tau_lo
    # prime with everything before the band so the first second is not blank
    while i < len(rows) and rows[i][0] // 1000 < lo_sec:
        rx_ms, _st, coin, bid, ask, bsz, asz = rows[i]
        L = legs[coin]
        L.bid, L.ask, L.bsz, L.asz, L.at = bid, ask, bsz, asz, rx_ms // 1000
        i += 1
    for sec in range(lo_sec, hi_sec + 1):
        while i < len(rows) and rows[i][0] // 1000 <= sec:
            rx_ms, _st, coin, bid, ask, bsz, asz = rows[i]
            L = legs[coin]
            L.bid, L.ask, L.bsz, L.asz, L.at = bid, ask, bsz, asz, rx_ms // 1000
            i += 1
        fresh = {}
        for c in COINS:
            L = legs[c]
            if L.at is None or sec - L.at > max_age:
                continue
            fresh[c] = (L.bid, L.ask, L.bsz, L.asz)
        out.append((close - sec, fresh))
    return out


def opportunities(states, min_size=1):
    """[(tau, side, contracts, profit_dollars, prices)] for every second where
    the basket is mispriced at `min_size` contracts or more.

    `contracts` is capped by the thinnest leg -- a basket is only as big as
    its smallest side."""
    found = []
    for tau, fresh in states:
        if len(fresh) < len(COINS):
            continue
        asks = [fresh[c][1] for c in COINS]
        asz = [fresh[c][3] for c in COINS]
        bids = [fresh[c][0] for c in COINS]
        bsz = [fresh[c][2] for c in COINS]
        if all(a > 0.0 and a < 1.0 and s > 0 for a, s in zip(asks, asz)):
            n = int(min(asz))
            if n >= min_size:
                p = basket_buy_profit(asks, n)
                if p > 0:
                    found.append((tau, "buy", n, p, tuple(asks)))
        if all(b > 0.0 and b < 1.0 and s > 0 for b, s in zip(bids, bsz)):
            n = int(min(bsz))
            if n >= min_size:
                p = basket_sell_profit(bids, n)
                if p > 0:
                    found.append((tau, "sell", n, p, tuple(bids)))
    return found


def runs_of(taus):
    """Group a sorted-descending list of taus into consecutive-second runs.

    An opportunity present at tau 40,39,38 is ONE chance lasting three
    seconds, not three chances. Counting seconds as events is how a single
    stale quote becomes a hundred trades on paper."""
    if not taus:
        return []
    t = sorted(set(taus), reverse=True)
    runs, cur = [], [t[0]]
    for x in t[1:]:
        if x == cur[-1] - 1:
            cur.append(x)
        else:
            runs.append(cur)
            cur = [x]
    runs.append(cur)
    return runs


# -------------------------------------------------------------- self-test
def _mk_line(rx_ms, stamp, coin, bid, ask, bsz, asz, spaced=False):
    """A synthetic ticker line. `spaced` uses json's default separators so the
    parser is exercised on both wire shapes."""
    obj = {
        "type": "ticker",
        "msg": {"market_ticker": "%s-%s-%s" % (SERIES, stamp, coin),
                "yes_bid_dollars": "%.4f" % bid, "yes_ask_dollars": "%.4f" % ask,
                "yes_bid_size_fp": "%.2f" % bsz, "yes_ask_size_fp": "%.2f" % asz,
                "ts": rx_ms // 1000},
        "_rx_ms": rx_ms}
    if spaced:
        return json.dumps(obj) + "\n"
    return json.dumps(obj, separators=(",", ":")) + "\n"


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    # --- the arithmetic ---------------------------------------------------
    ck(abs(order_fee(1, 0.50) - 0.02) < 1e-12,
       "fee at 50c is 0.07*0.25 = 1.75c, rounded up to 2c")
    ck(order_fee(100, 0.01) == math.ceil(0.07 * 100 * 0.01 * 0.99 * 100) / 100.0,
       "fee scales with contracts and rounds up once per order")
    ck(order_fee(0, 0.5) == 0.0, "no contracts, no fee")
    ck(abs(order_fee(1, 0.99) - order_fee(1, 0.01)) < 1e-12,
       "the fee is symmetric: buying a 1c leg costs what buying its 99c NO does")

    p = basket_buy_profit([0.90, 0.02, 0.02, 0.02, 0.02], 10)
    gross = 10 * (1.00 - 0.98)
    fees = order_fee(10, 0.90) + 4 * order_fee(10, 0.02)
    ck(abs(p - (gross - fees)) < 1e-12,
       "buy basket at 98c, 10 contracts: 20c gross less %.2f fees = %+.2f" % (fees, p))
    ck(p > 0, "and it is still positive after fees")
    ck(basket_buy_profit([0.20, 0.20, 0.20, 0.20, 0.20], 10) < 0,
       "a basket that sums to exactly $1.00 LOSES the fees -- never free")
    ck(basket_buy_profit([0.99, 0.02, 0.02, 0.02, 0.02], 10) < 0,
       "a basket summing to $1.07 loses 70c on 10 -- the common case")
    ck(basket_sell_profit([0.96, 0.03, 0.03, 0.03, 0.03], 10) > 0,
       "bids summing to $1.08: selling all five nets %+.2f"
       % basket_sell_profit([0.96, 0.03, 0.03, 0.03, 0.03], 10))
    ck(basket_sell_profit([0.90, 0.02, 0.02, 0.02, 0.02], 10) < 0,
       "bids summing to 98c: selling all five LOSES, correctly")

    # a hand-reconciled case, per the standing rule that a good number is
    # checked by hand before it is believed
    hand = 25 * 1.00 - 25 * (0.93 + 0.01 + 0.01 + 0.01 + 0.01) \
        - (math.ceil(0.07 * 25 * 0.93 * 0.07 * 100) / 100.0
           + 4 * (math.ceil(0.07 * 25 * 0.01 * 0.99 * 100) / 100.0))
    ck(abs(basket_buy_profit([0.93, 0.01, 0.01, 0.01, 0.01], 25) - hand) < 1e-12,
       "hand-reconciled: 25 baskets at 97c = $0.75 gross, fees $%.2f, net $%.2f"
       % (25 * 0.03 - hand, hand))

    # --- the line parser --------------------------------------------------
    r = _fields(_mk_line(1700000000123, "26SEP210100", "BTC", 0.9, 0.93, 40, 12))
    ck(r == (1700000000123, "26SEP210100", "BTC", 0.9, 0.93, 40.0, 12.0),
       "a ticker line parses to exactly its fields")
    ck(_fields(_mk_line(1700000000123, "26SEP210100", "BTC", 0.9, 0.93, 40, 12,
                        spaced=True)) == r,
       "and parses identically with whitespace after every colon")
    ck(_fields(REAL_LINE) ==
       (1789966800649, "26SEP210100", "XRP", 0.0, 0.01, 0.0, 78.0),
       "A LINE COPIED VERBATIM OFF THE TAPE parses to its true values -- "
       "the only test here that fails if the wire format moves")
    ck(_fields('{"type":"ticker","msg":{"market_ticker":"KXBTC15M-26SEP210100-T1"}}')
       is None, "a non-race ticker is skipped, not mangled")
    ck(_fields('{"type":"ticker","msg":{"market_ticker":"%s-26SEP210100-DOGE"}}'
               % SERIES) is None, "an unknown leg is skipped")
    ck(_fields('{"type":"ticker","msg":{"market_ticker":"%s-26SEP210100-BTC"}}'
               % SERIES) is None, "a line missing the price fields is refused")

    # --- close_of ---------------------------------------------------------
    import datetime as dt
    c = close_of("26SEP210100")
    ck(c is not None and dt.datetime.utcfromtimestamp(c) ==
       dt.datetime(2026, 9, 21, 5, 0), "26SEP210100 is 05:00 UTC -- the stamp is Eastern")
    ck(close_of("garbage") is None, "an unparseable stamp returns None")

    # --- has_offer / has_bid ---------------------------------------------
    L = Leg()
    L.ask, L.asz, L.at = 1.0, 0.0, 10
    ck(not L.has_offer(),
       "ask 1.0000 with size 0 is NO OFFER -- the empty-book print")
    L.ask, L.asz = 0.93, 0.0
    ck(not L.has_offer(), "a price with zero size is not an offer")
    L.asz = 5
    ck(L.has_offer(), "a price with size is")
    L.bid, L.bsz, L.at = 0.0, 0.0, 10
    ck(not L.has_bid(), "bid 0.0000 size 0 is no bid")

    # --- the scan, on a planted world ------------------------------------
    close = close_of("26SEP210100")
    stamp = "26SEP210100"

    def race_rows(sec_prices, size=20):
        rows = []
        for sec, prices in sec_prices.items():
            for coin, (b, a) in prices.items():
                rows.append(((close - sec) * 1000 * 0 + (sec) * 1000, stamp,
                             coin, b, a, size, size))
        return rows

    # world 1: a real arb planted at tau 40..38, nothing anywhere else
    pr_flat = {c: (0.01, 0.03) for c in COINS}
    pr_flat["BTC"] = (0.90, 0.95)            # sums: bids 0.94, asks 1.07 -> nothing
    pr_arb = {c: (0.01, 0.02) for c in COINS}
    pr_arb["BTC"] = (0.88, 0.90)             # asks sum 0.98 -> arb
    seq = {}
    for sec in range(close - 120, close):
        tau = close - sec
        seq[sec] = pr_arb if 38 <= tau <= 40 else pr_flat
    st = scan_race(race_rows(seq), close, tau_lo=1, tau_hi=120, max_age=30)
    opp = opportunities(st, min_size=1)
    buys = [o for o in opp if o[1] == "buy"]
    ck(len(opp) == len(buys) == 3,
       "PLANTED: exactly the three seconds with a 98c basket are found (%d)" % len(opp))
    ck(sorted(o[0] for o in buys) == [38, 39, 40],
       "and they are taus 38, 39, 40 -- the seconds it was actually there")
    ck(all(o[2] == 20 for o in buys), "size is the thinnest leg, 20")
    ck(len(runs_of([o[0] for o in buys])) == 1,
       "three consecutive seconds count as ONE opportunity lasting 3 s, not three")

    # world 2: NOTHING planted -- the estimator must find nothing
    seq2 = {sec: pr_flat for sec in range(close - 120, close)}
    st2 = scan_race(race_rows(seq2), close, tau_lo=1, tau_hi=120, max_age=30)
    ck(opportunities(st2, min_size=1) == [],
       "NULL: a world with no mispricing yields no opportunities")

    # world 3: a sell-side arb
    pr_rich = {c: (0.03, 0.05) for c in COINS}
    pr_rich["BTC"] = (0.97, 0.99)            # bids sum 1.09
    seq3 = {sec: pr_rich for sec in range(close - 120, close)}
    st3 = scan_race(race_rows(seq3), close, tau_lo=1, tau_hi=120, max_age=30)
    o3 = opportunities(st3, min_size=1)
    ck(o3 and all(o[1] == "sell" for o in o3),
       "bids summing to $1.09 are found as SELL baskets (%d seconds)" % len(o3))

    # world 4: STALENESS -- one leg goes quiet and the basket must stop counting
    seq4 = {}
    for sec in range(close - 120, close):
        p = dict(pr_arb)
        if close - sec < 60:
            p = {c: v for c, v in p.items() if c != "HYPE"}     # HYPE stops printing
        seq4[sec] = p
    st4 = scan_race(race_rows(seq4), close, tau_lo=1, tau_hi=120, max_age=10)
    o4 = opportunities(st4, min_size=1)
    ck(o4 and min(o[0] for o in o4) >= 49,
       "a leg that stops printing kills the basket ~10 s later (earliest tau %d, "
       "cap 10 s)" % (min(o[0] for o in o4) if o4 else -1))
    st4b = scan_race(race_rows(seq4), close, tau_lo=1, tau_hi=120, max_age=120)
    ck(len(opportunities(st4b, min_size=1)) > len(o4),
       "and a loose age cap counts those stale seconds -- which is why the "
       "real scan is run at several caps")

    # world 5: SIZE FLOOR
    st5 = scan_race(race_rows(seq, size=3), close, tau_lo=1, tau_hi=120, max_age=30)
    ck(opportunities(st5, min_size=1) and not opportunities(st5, min_size=10),
       "a 3-contract basket is found at min_size 1 and refused at 10")

    # world 6: nothing after the close may be read
    seq6 = {sec: pr_arb for sec in range(close, close + 60)}
    st6 = scan_race(race_rows(seq6), close, tau_lo=1, tau_hi=120, max_age=3600)
    ck(opportunities(st6, min_size=1) == [],
       "quotes stamped at or after the close are outside the band and ignored")

    # --- end-to-end through the file reader -------------------------------
    tmp = tempfile.mkdtemp(prefix="racebook_")
    try:
        d = os.path.join(tmp, "ticker")
        os.makedirs(d)
        with gzip.open(os.path.join(d, "20260921T05.jsonl.gz"), "wt") as fh:
            for sec in range(close - 120, close):
                pr = pr_arb if 38 <= close - sec <= 40 else pr_flat
                for coin, (b, a) in pr.items():
                    fh.write(_mk_line(sec * 1000, stamp, coin, b, a, 20, 20))
                fh.write('{"type":"ticker","msg":{"market_ticker":'
                         '"KXBTC15M-26SEP210100-T1","yes_bid_dollars":"0.5000",'
                         '"yes_ask_dollars":"0.5200","yes_bid_size_fp":"10.00",'
                         '"yes_ask_size_fp":"10.00"},"_rx_ms":%d}\n' % (sec * 1000))
        got = cached_hour(os.path.join(d, "20260921T05.jsonl.gz"),
                          cache_dir=os.path.join(tmp, "cache"))
        ck(len(got) == 120 * 5,
           "the reader pulls 600 race rows out of a file that also holds "
           "up/down tickers (%d)" % len(got))
        again = cached_hour(os.path.join(d, "20260921T05.jsonl.gz"),
                            cache_dir=os.path.join(tmp, "cache"))
        ck(again == got, "and the cache round-trips to exactly the same rows")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("racebook selftest:", "OK" if ok else "FAILED")
    return ok


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--hours", type=int, default=0,
                    help="only the most recent N hourly files (0 = all)")
    ap.add_argument("--tau-hi", type=int, default=900)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()

    if not selftest():
        return 1
    if a.selftest:
        return 0

    files = sorted(glob.glob(os.path.join(a.data, "ticker", "*.jsonl.gz")))
    if a.hours:
        files = files[-a.hours:]
    if not files:
        print("loaded nothing -- no ticker files under %s" % a.data)
        return 0
    print("\nreading %d hourly ticker files (%s .. %s)"
          % (len(files), os.path.basename(files[0]), os.path.basename(files[-1])))
    cand, got = parse_rate(files)
    print("  parser check on the 3 newest files: %d candidate lines, %d parsed "
          "(%.1f%%)" % (cand, got, 100.0 * got / cand if cand else 0.0))
    if cand and got < 0.95 * cand:
        print("REFUSING TO REPORT -- the ticker wire format no longer matches "
              "the parser. Fix _fields() before believing any number here.")
        return 1

    by_race = collections.defaultdict(list)
    n_rows = 0
    for k, fp in enumerate(files):
        for r in cached_hour(fp, cache_dir=None if a.no_cache else CACHE):
            by_race[r[1]].append(r)
            n_rows += 1
        if (k + 1) % 50 == 0:
            print("  ... %d/%d files, %d race quotes" % (k + 1, len(files), n_rows),
                  flush=True)
    if not n_rows:
        print("loaded nothing -- no CRYPTOLEAD ticker messages on disk")
        return 0
    print("  %d race quotes across %d races" % (n_rows, len(by_race)))

    # a race is only usable if we saw all five legs quote at least once
    races = []
    for stamp, rows in by_race.items():
        c = close_of(stamp)
        if c is None:
            continue
        if len({r[2] for r in rows}) < len(COINS):
            continue
        races.append((c, stamp, rows))
    races.sort()
    print("  %d races with all five legs quoting" % len(races))
    if len(races) < 30:
        print("loaded nothing -- too few complete races to say anything")
        return 0
    days = (races[-1][0] - races[0][0]) / 86400.0

    # ---------------- where does the basket sum actually sit? -------------
    print("\n## 1. WHERE THE BASKET SUM SITS  (all five legs quoting, age <= %ds)"
          % DEFAULT_AGE)
    print("The five YES asks must sum to MORE than $1.00 or the book is giving")
    print("money away; the five YES bids must sum to LESS. How close does it get?")
    hist = collections.defaultdict(lambda: [0, 0, 0.0, 0.0, [], []])
    for c, stamp, rows in races:
        st = scan_race(rows, c, tau_lo=1, tau_hi=a.tau_hi, max_age=DEFAULT_AGE)
        for tau, fresh in st:
            if len(fresh) < len(COINS):
                continue
            asks = [fresh[x][1] for x in COINS]
            bids = [fresh[x][0] for x in COINS]
            asz = [fresh[x][3] for x in COINS]
            bsz = [fresh[x][2] for x in COINS]
            band = ("0-60s" if tau <= 60 else "1-5m" if tau <= 300 else "5m+")
            h = hist[band]
            h[0] += 1
            if all(x > 0 and y > 0 for x, y in zip(asks, asz)):
                h[4].append(sum(asks))
            if all(x > 0 and y > 0 for x, y in zip(bids, bsz)):
                h[5].append(sum(bids))

    def pct(v, q):
        if not v:
            return float("nan")
        v = sorted(v)
        i = max(0, min(len(v) - 1, int(q * (len(v) - 1) + 0.5)))
        return v[i]

    print("  %-8s %9s %9s %8s %8s %8s %8s %8s"
          % ("tau band", "seconds", "n asks", "p01", "p05", "median", "p95", "min"))
    for band in ("0-60s", "1-5m", "5m+"):
        h = hist.get(band)
        if not h:
            continue
        v = h[4]
        print("  %-8s %9d %9d %7.3f %7.3f %8.3f %7.3f %7.3f"
              % (band + " ask", h[0], len(v), pct(v, 0.01), pct(v, 0.05),
                 pct(v, 0.50), pct(v, 0.95), min(v) if v else float("nan")))
        v = h[5]
        print("  %-8s %9s %9d %7.3f %7.3f %8.3f %7.3f %7.3f"
              % (band + " bid", "", len(v), pct(v, 0.05), pct(v, 0.50),
                 pct(v, 0.95), pct(v, 0.99), max(v) if v else float("nan")))
    print("  (ask rows show the LOW tail -- that is where free money would be;")
    print("   bid rows show the HIGH tail, p05/median/p95/p99 then the max.)")

    # ---------------- the opportunities ------------------------------------
    print("\n## 2. RISKLESS BASKETS FOUND  (%.1f days of tape)" % days)
    print("A run of consecutive seconds is ONE opportunity, not one per second.")
    for age in AGES:
        # one pass over the tape per age cap; the per-second states are never
        # kept (900 s x thousands of races would not fit beside the collector)
        raw = []
        for c, stamp, rows in races:
            st = scan_race(rows, c, tau_lo=1, tau_hi=a.tau_hi, max_age=age)
            o = opportunities(st, min_size=min(SIZES))
            if o:
                raw.append((stamp, o))
        for msz in SIZES:
            allo = [(s, [x for x in o if x[2] >= msz]) for s, o in raw]
            allo = [(s, o) for s, o in allo if o]
            n_buy = n_sell = 0
            dollars = 0.0
            secs = 0
            best = None
            durs = []
            for stamp, o in allo:
                for side in ("buy", "sell"):
                    taus = [x[0] for x in o if x[1] == side]
                    if not taus:
                        continue
                    for run in runs_of(taus):
                        durs.append(len(run))
                        if side == "buy":
                            n_buy += 1
                        else:
                            n_sell += 1
                        # value the run once, at its best second
                        v = max(x[3] for x in o if x[1] == side and x[0] in run)
                        dollars += v
                        if best is None or v > best[0]:
                            best = (v, stamp, side, run[0])
                    secs += len(taus)
            print("  age<=%-4ds size>=%-3d  buys %4d  sells %4d  seconds %6d  "
                  "ceiling $%8.2f  = $%6.2f/day  median run %ss"
                  % (age, msz, n_buy, n_sell, secs, dollars, dollars / days if days else 0,
                     ("%.0f" % pct(durs, 0.5)) if durs else "-"))
            if best and age == DEFAULT_AGE and msz == 10:
                print("       best single: $%.2f  %s  %s side at tau %d"
                      % (best[0], best[1], best[2], best[3]))
    print("\n  DOLLARS ARE A CEILING. They assume the advertised top-of-book size")
    print("  is ours and that all five legs fill. Nothing here is a fill rate.")

    # ---------------- how long do they last? ------------------------------
    print("\n## 3. HOW LONG AN OPPORTUNITY LIVES  (age<=%ds, size>=10)" % DEFAULT_AGE)
    print("Five orders cannot be sent at once. Anything under ~3 s is not")
    print("tradeable with a REST leg-in; this is the number that decides it.")
    durs = collections.Counter()
    for c, stamp, rows in races:
        st = scan_race(rows, c, tau_lo=1, tau_hi=a.tau_hi, max_age=DEFAULT_AGE)
        o = opportunities(st, min_size=10)
        for side in ("buy", "sell"):
            for run in runs_of([x[0] for x in o if x[1] == side]):
                durs[min(len(run), 30)] += 1
    if durs:
        tot = sum(durs.values())
        cum = 0
        print("  %6s %8s %8s" % ("secs", "count", "cum %"))
        for k in sorted(durs):
            cum += durs[k]
            print("  %6d %8d %7.1f%%" % (k, durs[k], 100.0 * cum / tot))
    else:
        print("  none found at size 10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
