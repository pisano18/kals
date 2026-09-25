"""polypaper.py -- a forward, real-time PAPER pin bot for Polymarket US's BTC
15-minute up/down market. READ-ONLY: it never sends an order anywhere.

WHAT IT DOES, every second of the last 45 seconds of each 15-minute window:
  * reads Polymarket US's real-time book for the window from their market
    WebSocket (wss://api.polymarket.us/v1/ws/markets), authenticated with the
    operator's READ key exactly as C:\\kals\\poly_us.py signs a GET;
  * reads the CF Benchmarks BRTI index from the recorder's own tape
    (C:\\kals\\kalshi_data\\cfbenchmarks_value, current hour, read-only, tailed
    incrementally -- the file is opened 'rb' and never written);
  * prices the window with pinrun's OWN fair() -- the same function the live
    bot calls, fed through pinrun's own IndexWS (on_frame), so the number is
    not a re-implementation;
  * applies the live bot's entry gates (argv of restart_bot.ps1, v-zerotake):
    confidence >= PIN, tau 3..45, edge floor, against-thin, jump gate, dump
    guard, early leg (tau > 30) price >= 95c and edge <= 10c, 10c edge cap
    above 20 s, 98c price ceiling, EV floor -- with POLYMARKET's taker fee
    0.0695*p*(1-p) in place of Kalshi's;
  * logs side, best ask, size, fee, edge, EV, would-buy and every refusal;
  * logs Kalshi KXBTC15M's best ask for the same side AT THE SAME SECOND from
    the recorder's ticker tape, and runs the same gates on it (Kalshi fee), so
    the two venues are compared second for second;
  * at the close: settles from the tape (mean of the 60 BRTI prints
    [close-60, close-1], rounded to 2 dp, Up if >= price-to-beat) and from
    Polymarket's own settlementPrice (GET /v1/market/slug/{slug}), and books
    the paper P&L of the FIRST second that would have bought.

WHAT IT DOES NOT MODEL (stated, not hidden): whether a real order would have
been filled (someone else may take the offer first -- live Kalshi fill rate is
~70%), bank-based sizing, the per-close budget, second buys / late adds,
hedging, the spike and toxic-flow gates. The P&L is "the offer was there and
we took it at the touch", which is the population CLAUDE.md rule 5 warns is
kinder than live fills. It is a forward tool for the venue question, not a
loss-rate measurement.

    python research/polypaper.py --selftest
    python research/polypaper.py --windows 1              # one window, foreground
    python research/polypaper.py --minutes 4320           # 3 days (stop file ends it)
    python research/polypaper.py --report [paths...]

Stop file: results/polypaper.stop (checked every second).
Logs: results/polypaper-<UTC start>.jsonl (one JSON object per line, UTC).
"""
import argparse
import asyncio
import decimal
import glob
import gzip
import io
import json
import math
import os
import statistics
import sys
import threading
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrun  # noqa: E402  (fair, IndexWS, gates -- imported, never edited)

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
TAPE = r"C:\kals\kalshi_data"
POLY_DIR = r"C:\kals"
STOP = os.path.join(RESULTS, "polypaper.stop")
WS_URL = "wss://api.polymarket.us/v1/ws/markets"
WS_PATH = "/v1/ws/markets"
IID = "BRTI"
KSERIES = "KXBTC15M"

POLY_TAKER = 0.0695            # docs.polymarket.us/fees.md
KALSHI_TAKER = 0.07
WINDOW_TAU = 45                # live --early-tau 45
EARLY_MIN_PRICE = 0.95         # live --early-min-price 0.95 (tau > TAU_MAX)
EARLY_MAX_EDGE_C = 10.0        # live --early-max-edge 10.0
ROUND_DIGITS = 2               # both venues: average rounded to 2 dp, >= wins
PAPER_SIZE = 10                # contracts per paper entry (~$60 funded)


# ------------------------------------------------------------------ fees / EV
def poly_fee(p):
    """Polymarket US taker fee per contract, raw formula."""
    return POLY_TAKER * p * (1.0 - p)


def poly_fee_order(p, n):
    """Billed on the order, banker's rounding to the cent (their docs)."""
    raw = decimal.Decimal(repr(POLY_TAKER * n * p * (1.0 - p)))
    return float(raw.quantize(decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_EVEN))


def kalshi_fee(p):
    return pinrun.billed_fee(p, 1)


def ev_of(price, fee, flip=None):
    """pinrun.expected_value's formula with the venue's fee passed in."""
    f = pinrun.MEASURED_FLIP if flip is None else flip
    return (1.0 - f) * (1.0 - price) - f * price - fee


# ------------------------------------------------------------------ time names
def us_eastern_offset(t):
    """Seconds to ADD to UTC for US Eastern (EDT -4h, EST -5h), by the US rule:
    DST from the 2nd Sunday of March 02:00 local to the 1st Sunday of
    November 02:00 local."""
    y = time.gmtime(t).tm_year

    def nth_sunday(month, n):
        wd = time.gmtime(_timegm(y, month, 1)).tm_wday          # Mon=0
        return 1 + (6 - wd) % 7 + 7 * (n - 1)
    start = _timegm(y, 3, nth_sunday(3, 2), 7)      # 02:00 EST == 07:00 UTC
    end = _timegm(y, 11, nth_sunday(11, 1), 6)      # 02:00 EDT == 06:00 UTC
    return -4 * 3600 if start <= t < end else -5 * 3600


def _timegm(y, mo, d, h=0, mi=0, s=0):
    import calendar
    return calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0))


def kalshi_prefix(close_s):
    """KXBTC15M ticker stem for the market closing at close_s (named in ET)."""
    et = time.gmtime(close_s + us_eastern_offset(close_s))
    return "%s-%02d%s%02d%02d%02d-" % (KSERIES, et.tm_year % 100,
                                        time.strftime("%b", et).upper(),
                                        et.tm_mday, et.tm_hour, et.tm_min)


def slug_for(start_s):
    return "cpc-btc-updown-15m-" + time.strftime("%Y-%m-%d-%H%Mz", time.gmtime(start_s))


def et_str(t):
    return time.strftime("%H:%M:%S", time.gmtime(t + us_eastern_offset(t))) + " ET"


# ------------------------------------------------------------------ tape tail
class GzTail:
    """Incremental reader of a gzip file that another process is still
    appending to with per-write flushes. Opened 'rb', never written. Returns
    only COMPLETE lines; a torn last block simply waits for more bytes. A
    zlib error (real corruption) stops this file and is counted, never
    raised into the loop."""

    def __init__(self, path):
        self.path = path
        self.pos = 0
        self.d = zlib.decompressobj(31)
        self.buf = b""
        self.errors = 0
        self.dead = False
        self.more = False

    def poll(self, max_bytes=256 << 10):
        """Complete lines from at most `max_bytes` of new compressed input.
        Call again while `self.more` is True (the read filled the chunk) --
        chunking keeps a whole hour's first read to a few MB of memory."""
        self.more = False
        if self.dead or not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "rb") as fh:
                fh.seek(self.pos)
                raw = fh.read(max_bytes)
        except OSError:
            return []
        if not raw:
            return []
        self.more = len(raw) == max_bytes
        self.pos += len(raw)
        out = b""
        try:
            while raw:
                out += self.d.decompress(raw)
                if self.d.eof:                  # a new gzip member follows
                    raw = self.d.unused_data
                    self.d = zlib.decompressobj(31)
                else:
                    raw = b""
        except zlib.error:
            self.errors += 1
            self.dead = True
        self.buf += out
        if b"\n" not in self.buf:
            return []
        body, self.buf = self.buf.rsplit(b"\n", 1)
        return body.decode("utf-8", "replace").split("\n")


class TapeFeed:
    """BRTI prints -> a pinrun.IndexWS (via its own on_frame), and the latest
    KXBTC15M ticker row per market, from the recorder's hourly files."""

    def __init__(self, idx, tape=TAPE):
        self.idx = idx
        self.tape = tape
        self.tails = {}                     # (channel, hour) -> GzTail
        self.kq = {}                        # ticker -> list of (rx_s, ybid, ybsz, yask, yasz)
        self.last_brti_rx = None

    def _file(self, chan, hour):
        return os.path.join(self.tape, chan, time.strftime("%Y%m%dT%H", time.gmtime(hour * 3600)) + ".jsonl.gz")

    def poll(self, now=None):
        now = time.time() if now is None else now
        h = int(now) // 3600
        for chan in ("cfbenchmarks_value", "ticker"):
            for hh in (h - 1, h):
                key = (chan, hh)
                if key not in self.tails:
                    self.tails[key] = GzTail(self._file(chan, hh))
                tl = self.tails[key]
                while True:
                    for line in tl.poll():
                        self._line(chan, line)
                    if not tl.more:
                        break
        for key in [k for k in self.tails if k[1] < h - 1]:
            del self.tails[key]

    def _line(self, chan, line):
        if chan == "cfbenchmarks_value":
            if '"BRTI"' not in line:
                return
            try:
                d = json.loads(line)
            except ValueError:
                return
            self.idx.on_frame(d, rx_ms=d.get("_rx_ms"))
            self.last_brti_rx = (d.get("_rx_ms") or 0) / 1000.0
        else:
            if KSERIES + "-" not in line:
                return
            try:
                d = json.loads(line)
                m = d["msg"]
                tk = m["market_ticker"]
                row = (d["_rx_ms"] / 1000.0, _f(m.get("yes_bid_dollars")), _f(m.get("yes_bid_size_fp")),
                       _f(m.get("yes_ask_dollars")), _f(m.get("yes_ask_size_fp")))
            except (ValueError, KeyError, TypeError):
                return
            q = self.kq.setdefault(tk, [])
            q.append(row)
            if len(q) > 4000:
                del q[:2000]

    def kalshi_at(self, close_s, t):
        """Newest KXBTC15M ticker row for this close received at or before t."""
        pre = kalshi_prefix(close_s)
        best = None
        for tk, q in self.kq.items():
            if not tk.startswith(pre):
                continue
            for row in reversed(q):
                if row[0] <= t:
                    if best is None or row[0] > best[1][0]:
                        best = (tk, row)
                    break
        return best


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ book
def parse_book(md):
    """Polymarket MARKET_DATA -> (bids desc, offers asc) of (price, qty), in
    Up (long) terms. Buying Down = selling Up at the bid: Down ask = 1 - bid."""
    bids = sorted(((_f(x["px"]["value"]), _f(x["qty"])) for x in md.get("bids") or []), reverse=True)
    asks = sorted((_f(x["px"]["value"]), _f(x["qty"])) for x in (md.get("offers") or md.get("asks") or []))
    return [b for b in bids if b[0] is not None], [a for a in asks if a[0] is not None]


def side_ask(bids, asks, want):
    """(price, size) of the cheapest way to BUY `want` ('yes'=Up, 'no'=Down)."""
    if want == "yes":
        return (asks[0][0], asks[0][1]) if asks else (None, 0.0)
    return (round(1.0 - bids[0][0], 4), bids[0][1]) if bids else (None, 0.0)


# ------------------------------------------------------------------ decision
def decide(f, price, size, tau, fee, strike, spot, sigma, moves):
    """The live bot's entry gates, in its order, on one venue's offer.
    Returns (want, edge, ev, refusals[]). An empty refusal list = would buy."""
    if f is None:
        return None, None, None, ["no_fair"]
    if f >= pinrun.PIN:
        want = "yes"
    elif f <= 1.0 - pinrun.PIN:
        want = "no"
    else:
        return None, None, None, ["confidence"]
    ref = []
    if not (pinrun.TAU_MIN <= tau <= WINDOW_TAU):
        ref.append("tau")
    if price is None or not size or price >= 1.0:
        return want, None, None, ref + ["no_offer"]
    gross = (f - price) if want == "yes" else ((1.0 - f) - price)
    edge = gross - fee
    ev = ev_of(price, fee)
    if edge < pinrun.EDGE_FLOOR:
        ref.append("edge_floor")
    a = pinrun.against_us(strike, spot, sigma, want)
    if a is not None and a >= pinrun.AGAINST_SIGMA and edge < pinrun.AGAINST_EDGE:
        ref.append("against_thin")
    j = pinrun.jump_against(moves, sigma, want)
    if j is not None and j >= pinrun.JUMP_SIGMA:          # live runs --jump-gate
        ref.append("jump_against")
    if gross > pinrun.DUMP_DISCOUNT:
        ref.append("dump_guard")
    early = tau > pinrun.TAU_MAX
    if early and price < EARLY_MIN_PRICE:
        ref.append("early_min_price")
    if early and 100.0 * edge > EARLY_MAX_EDGE_C:
        ref.append("early_wide")
    if pinrun.edge_cap_block(edge, cap_c=10.0, tau=tau, cap_tau=20):
        ref.append("edge_cap")
    if price > pinrun.PRICE_CEILING:
        ref.append("price_ceiling")
    if ev < pinrun.EV_FLOOR:
        ref.append("ev_floor")
    return want, edge, ev, ref


def paper_pnl(price, n, won, fee_fn=poly_fee_order):
    fee = fee_fn(price, n)
    return round((n * (1.0 - price) if won else -n * price) - fee, 4), fee


# ------------------------------------------------------------------ the bot
class Bot:
    def __init__(self, log_path, windows=None, minutes=60.0, size=PAPER_SIZE, get_fn=None):
        self.idx = pinrun.IndexWS([IID])
        self.tape = TapeFeed(self.idx)
        self.books = {}                  # slug -> (rx, bids, asks)
        self.trades = {}                 # slug -> count
        self.log_path = log_path
        self.windows_left = windows
        self.t_end = time.time() + 60.0 * minutes
        self.size = size
        self.state = {}                  # close_s -> dict
        self.get_fn = get_fn
        self.ws_frames = 0
        self.ws_errors = 0
        self.done = False

    def rec(self, **kw):
        kw.setdefault("t", round(time.time(), 3))
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(kw, separators=(",", ":")) + "\n")

    # -- Polymarket REST (GET only, via poly_us)
    def _poly_get(self, path, q=""):
        if self.get_fn:
            return self.get_fn(path, q)
        sys.path.insert(0, POLY_DIR)
        import poly_us
        return poly_us.get(path, q)

    def market_terms(self, slug):
        st, b = self._poly_get("/v1/market/slug/" + slug)
        if st != 200 or not isinstance(b, dict):
            return None, None
        m = b.get("market") if isinstance(b.get("market"), dict) else b
        apt = m.get("assetPriceTerms") or {}
        return _f((apt.get("priceToBeat") or {}).get("value")), _f((apt.get("settlementPrice") or {}).get("value"))

    # -- the per-second step
    def step(self, now):
        self.tape.poll(now)
        now_s = int(now)
        close_s = (now_s // 900 + 1) * 900
        tau = close_s - now_s
        st = self.state.get(close_s)
        if st is None:
            st = self.state[close_s] = {"slug": slug_for(close_s - 900), "ptb": None, "ptb_try": 0,
                                        "entry": None, "k_entry": None, "secs": 0, "settled": False}
        if st["ptb"] is None and st["ptb_try"] < 5 and tau <= 880:
            st["ptb_try"] += 1
            try:
                st["ptb"], _ = self.market_terms(st["slug"])
            except Exception as e:                               # noqa: BLE001
                self.rec(type="error", where="ptb", err=str(e)[:200])
        if tau <= WINDOW_TAU:
            self.second(close_s, st, now, now_s, tau)
        for cs, s2 in list(self.state.items()):
            if cs < now_s - 1 and not s2["settled"]:
                self.settle(cs, s2, now)

    def tape_strike(self, close_s):
        start = close_s - 900
        d = self.idx.ticks.get(IID) or {}
        got = [d[s] for s in range(start - pinrun.N_AVG, start) if s in d]
        if len(got) < pinrun.N_AVG:
            return None
        return round(sum(got) / pinrun.N_AVG, 2)

    def second(self, close_s, st, now, now_s, tau):
        slug = st["slug"]
        strike = st["ptb"] if st["ptb"] is not None else self.tape_strike(close_s)
        sig = self.idx.sigma(IID)
        f = None
        if strike is not None and sig:
            f = pinrun.fair(self.idx, IID, close_s, now_s, strike, sig * pinrun.SIGMA_STRESS,
                            round_digits=ROUND_DIGITS)
        _, spot, age = self.idx.spot(IID)
        moves = self.idx.recent_moves(IID, pinrun.JUMP_LOOKBACK)
        bk = self.books.get(slug)
        bids, asks = (bk[1], bk[2]) if bk else ([], [])
        want0 = "yes" if (f is not None and f >= 0.5) else "no"
        p_px, p_sz = side_ask(bids, asks, want0)
        pw, pedge, pev, pref = decide(f, p_px, p_sz, tau, poly_fee(p_px) if p_px else 0.0,
                                      strike, spot, sig, moves)
        kr = self.tape.kalshi_at(close_s, now)
        k_px = k_sz = k_tk = k_age = None
        if kr:
            k_tk, (rx, yb, ybs, ya, yas) = kr
            k_age = round(now - rx, 2)
            if want0 == "yes":
                k_px, k_sz = ya, yas
            else:
                k_px, k_sz = (round(1.0 - yb, 4) if yb is not None else None), ybs
        kw, kedge, kev, kref = decide(f, k_px, k_sz, tau, kalshi_fee(k_px) if k_px else 0.0,
                                      strike, spot, sig, moves)
        p_buy = pw is not None and not pref
        k_buy = kw is not None and not kref
        st["secs"] += 1
        r = dict(type="sec", close=close_s, slug=slug, tau=tau, strike=strike, ptb=st["ptb"],
                 spot=spot, idx_age=None if age is None else round(age, 2),
                 sigma=None if sig is None else round(sig, 4), fair=None if f is None else round(f, 6),
                 side=pw or (want0 if f is not None else None),
                 p_ask=p_px, p_size=p_sz, p_fee=None if p_px is None else round(poly_fee(p_px), 5),
                 p_edge=None if pedge is None else round(pedge, 5), p_ev=None if pev is None else round(pev, 5),
                 p_buy=p_buy, p_why=pref, p_book_age=None if not bk else round(now - bk[0], 2),
                 p_bid=bids[0][0] if bids else None, p_bid_sz=bids[0][1] if bids else None,
                 p_offer=asks[0][0] if asks else None, p_offer_sz=asks[0][1] if asks else None,
                 k_ticker=k_tk, k_ask=k_px, k_size=k_sz, k_age=k_age,
                 k_fee=None if k_px is None else round(kalshi_fee(k_px), 5),
                 k_edge=None if kedge is None else round(kedge, 5), k_buy=k_buy, k_why=kref)
        self.rec(**r)
        if p_buy and st["entry"] is None:
            n = min(float(self.size), float(p_sz))
            st["entry"] = {"side": pw, "price": p_px, "n": n, "tau": tau, "fair": f, "edge": pedge}
            self.rec(type="paper_buy", venue="polymarket", close=close_s, slug=slug, side=pw, price=p_px,
                     n=n, tau=tau, fair=round(f, 6), edge=round(pedge, 5),
                     fee_order=poly_fee_order(p_px, n))
        if k_buy and st["k_entry"] is None:
            n = min(float(self.size), float(k_sz))
            st["k_entry"] = {"side": kw, "price": k_px, "n": n, "tau": tau}
            self.rec(type="paper_buy", venue="kalshi", close=close_s, ticker=k_tk, side=kw, price=k_px,
                     n=n, tau=tau, fair=round(f, 6), edge=round(kedge, 5))

    def settle(self, close_s, st, now):
        d = self.idx.ticks.get(IID) or {}
        got = [d[s] for s in range(close_s - pinrun.N_AVG, close_s) if s in d]
        if len(got) < pinrun.N_AVG and now < close_s + 20:
            return                                   # prints still arriving
        tape_settle = round(sum(got) / len(got), 2) if got else None
        poly_settle = None
        if st["secs"] > 0:
            if now < st.get("settle_next", 0):
                return                               # one settlement GET per 5 s at most
            st["settle_next"] = now + 5.0
            try:
                _, poly_settle = self.market_terms(st["slug"])
            except Exception:                        # noqa: BLE001
                poly_settle = None
            if poly_settle is None and now < close_s + 90:
                return                               # Polymarket publishes a little late
        st["settled"] = True
        if st["secs"] == 0:
            return                                   # a window we never watched
        strike = st["ptb"] if st["ptb"] is not None else self.tape_strike(close_s)
        final = poly_settle if poly_settle is not None else tape_settle
        up = None if (final is None or strike is None) else (final >= strike)
        out = dict(type="settle", close=close_s, slug=st["slug"], strike=strike,
                   tape_strike=self.tape_strike(close_s), tape_settle=tape_settle,
                   tape_prints=len(got), poly_settle=poly_settle, up=up, secs=st["secs"])
        for key, venue, fee_fn in (("entry", "p", poly_fee_order),
                                   ("k_entry", "k", lambda p, n: round(n * kalshi_fee(p), 4))):
            e = st[key]
            if e and up is not None:
                won = (e["side"] == "yes") == up
                pnl, fee = paper_pnl(e["price"], e["n"], won, fee_fn)
                out[venue + "_pnl"] = pnl
                out[venue + "_won"] = won
                out[venue + "_entry"] = e
        self.rec(**out)
        if self.windows_left is not None:
            self.windows_left -= 1
            if self.windows_left <= 0:
                self.done = True

    # -- Polymarket WebSocket (read-only market data)
    async def ws_loop(self):
        import websockets
        sys.path.insert(0, POLY_DIR)
        import poly_us
        while not self.done and not os.path.exists(STOP) and time.time() < self.t_end:
            try:
                c = json.load(open(poly_us.CREDS, encoding="utf-8-sig"))
                hdrs = poly_us.headers(c["key_id"], poly_us.load_key(c["secret"]), "GET", WS_PATH)
                async with websockets.connect(WS_URL, additional_headers=hdrs, max_size=8_000_000,
                                              ping_interval=20) as ws:
                    self.rec(type="ws", ev="connected")
                    done_subs = set()   # slugs this connection already subscribed
                    while not self.done and not os.path.exists(STOP) and time.time() < self.t_end:
                        st15 = int(time.time()) // 900 * 900
                        want = [x for x in (slug_for(st15), slug_for(st15 + 900)) if x not in done_subs]
                        if want:
                            # ONLY new slugs: a request repeating one already
                            # subscribed is rejected whole (2026-09-25 fix)
                            for i, styp in enumerate(("SUBSCRIPTION_TYPE_MARKET_DATA", "SUBSCRIPTION_TYPE_TRADE")):
                                await ws.send(json.dumps({"subscribe": {
                                    "requestId": "pp-%d-%d" % (int(time.time()), i), "subscriptionType": styp,
                                    "marketSlugs": want, "responsesDebounced": False}}))
                            self.rec(type="ws", ev="subscribed", slugs=want)
                            done_subs.update(want)
                        try:
                            frame = await asyncio.wait_for(ws.recv(), timeout=2)
                        except asyncio.TimeoutError:
                            continue
                        self.on_ws(frame, time.time())
            except Exception as e:                           # noqa: BLE001
                self.ws_errors += 1
                self.rec(type="ws", ev="error", err=str(e)[:300])
                await asyncio.sleep(3)

    def on_ws(self, frame, rx):
        try:
            fr = json.loads(frame)
        except (ValueError, TypeError):
            return
        self.ws_frames += 1
        md = fr.get("marketData")
        if md and md.get("marketSlug"):
            bids, asks = parse_book(md)
            self.books[md["marketSlug"]] = (rx, bids, asks)
        tr = fr.get("trade")
        if tr and tr.get("marketSlug"):
            self.trades[tr["marketSlug"]] = self.trades.get(tr["marketSlug"], 0) + 1

    async def tick_loop(self):
        while not self.done and not os.path.exists(STOP) and time.time() < self.t_end:
            now = time.time()
            await asyncio.sleep(max(0.0, 1.0 - (now % 1.0)) + 0.35)   # 0.35 s into each second
            try:
                await asyncio.get_running_loop().run_in_executor(None, self.step, time.time())
            except Exception as e:                           # noqa: BLE001
                self.rec(type="error", where="step", err=repr(e)[:300])
        self.done = True

    async def main(self):
        self.tape.poll()
        self.rec(type="start", pid=os.getpid(), size=self.size, windows=self.windows_left,
                 pin=pinrun.PIN, tau_min=pinrun.TAU_MIN, window_tau=WINDOW_TAU,
                 ceiling=pinrun.PRICE_CEILING, edge_floor=pinrun.EDGE_FLOOR, ev_floor=pinrun.EV_FLOOR,
                 flip=pinrun.MEASURED_FLIP, sigma_ruler=pinrun.SIGMA_RULER, poly_fee=POLY_TAKER,
                 brti_prints=len(self.idx.ticks.get(IID) or {}))
        await asyncio.gather(self.ws_loop(), self.tick_loop())
        self.rec(type="end", ws_frames=self.ws_frames, ws_errors=self.ws_errors,
                 tape_errors=sum(t.errors for t in self.tape.tails.values()))


# ------------------------------------------------------------------ report
def report(paths=None, out=print):
    paths = paths or sorted(glob.glob(os.path.join(RESULTS, "polypaper-*.jsonl")))
    wins = {}
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("type") == "sec":
                    w = wins.setdefault(r["close"], {"secs": [], "settle": None})
                    w["secs"].append(r)
                elif r.get("type") == "settle":
                    wins.setdefault(r["close"], {"secs": [], "settle": None})["settle"] = r
    tot_p = tot_k = 0.0
    n_p = n_k = 0
    lines = []
    for cs in sorted(wins):
        w = wins[cs]
        s = w["settle"] or {}
        secs = w["secs"]
        pb = [r for r in secs if r.get("p_buy")]
        kb = [r for r in secs if r.get("k_buy")]
        conf = [r for r in secs if r.get("fair") is not None and (r["fair"] >= pinrun.PIN or r["fair"] <= 1 - pinrun.PIN)]
        both = [r for r in conf if r.get("p_ask") is not None and r.get("k_ask") is not None]
        pa = [r["p_ask"] for r in both]
        ka = [r["k_ask"] for r in both]
        why = {}
        for r in conf:
            for g in r.get("p_why") or []:
                why[g] = why.get(g, 0) + 1
        lines.append("close %s (%s)  strike %s settle %s (tape %s)  %s" % (
            time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(cs)), et_str(cs), s.get("strike"),
            s.get("poly_settle"), s.get("tape_settle"),
            {True: "UP", False: "DOWN", None: "unsettled"}[s.get("up")]))
        lines.append("  seconds logged %d | model sure enough (>= %.1f%%) %d | Poly would buy %d | Kalshi would buy %d"
                     % (len(secs), 100 * pinrun.PIN, len(conf), len(pb), len(kb)))
        if both:
            lines.append("  same-second ask on the sure side: Poly median %.2f, Kalshi median %.2f (%d seconds both quoted)"
                         % (statistics.median(pa), statistics.median(ka), len(both)))
        if why:
            lines.append("  Poly refusals (seconds): " + ", ".join("%s %d" % kv for kv in sorted(why.items(), key=lambda x: -x[1])))
        for v, lab in (("p", "Polymarket"), ("k", "Kalshi")):
            if (v + "_pnl") in s:
                e = s[v + "_entry"]
                lines.append("  %s paper buy: %s %g @ %.2f at %ds left -> %s, P&L $%+.2f" % (
                    lab, e["side"], e["n"], e["price"], e["tau"], "won" if s[v + "_won"] else "LOST", s[v + "_pnl"]))
                if v == "p":
                    tot_p += s["p_pnl"]
                    n_p += 1
                else:
                    tot_k += s["k_pnl"]
                    n_k += 1
    lines.append("TOTAL windows %d | Polymarket paper entries %d, P&L $%+.2f | Kalshi paper entries %d, P&L $%+.2f"
                 % (len(wins), n_p, tot_p, n_k, tot_k))
    for ln in lines:
        out(ln)
    return wins


# ------------------------------------------------------------------ self-test
def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and bool(c)

    # -- 1. time names
    ck(kalshi_prefix(_timegm(2026, 9, 25, 8, 15)) == "KXBTC15M-26SEP250415-",
       "Kalshi ticker stem is named in EDT in September (08:15Z -> 0415)")
    ck(kalshi_prefix(_timegm(2026, 12, 1, 13, 0)) == "KXBTC15M-26DEC010800-",
       "and in EST in December (13:00Z -> 0800)")
    ck(slug_for(_timegm(2026, 9, 25, 7, 45)) == "cpc-btc-updown-15m-2026-09-25-0745z",
       "Polymarket slug is the window START")

    # -- 2. fees and paper P&L arithmetic, by hand
    ck(abs(poly_fee(0.97) - 0.0695 * 0.97 * 0.03) < 1e-12, "Poly taker fee 0.0695*p*(1-p)")
    ck(poly_fee_order(0.97, 10) == 0.02 and poly_fee_order(0.97, 1) == 0.0,
       "order fee banker-rounds to the cent: 10 @ 97c -> $0.02, 1 @ 97c -> $0.00")
    ck(paper_pnl(0.97, 10, True) == (0.28, 0.02) and paper_pnl(0.97, 10, False) == (-9.72, 0.02),
       "10 contracts @ 97c: win +$0.28, loss -$9.72")

    # -- 3. a planted index through pinrun's OWN IndexWS + fair()
    close = _timegm(2026, 9, 25, 8, 15)
    idx = pinrun.IndexWS([IID])
    import random
    rnd = random.Random(7)
    lvl = 84000.0
    vals = {}
    for s in range(close - 1200, close - 25 + 1):      # prints up to tau 25
        lvl += rnd.gauss(0, 2.0)
        vals[s] = lvl
        idx.on_frame({"type": "cfbenchmarks_value", "msg": {"index_id": IID, "data": json.dumps(
            {"type": "value", "time": s * 1000, "id": IID, "value": "%.2f" % lvl})}}, rx_ms=s * 1000)
    now_s = close - 25
    sig = idx.sigma(IID)
    lo = close - 60
    locked = sum(float("%.2f" % vals[s]) for s in range(lo, now_s + 1))
    r = close - 1 - now_s
    spot = float("%.2f" % vals[now_s])
    mu = (locked + r * spot) / 60.0
    K_far = round(mu - 200.0, 2)                       # far below: Up is certain
    f = pinrun.fair(idx, IID, close, now_s, K_far, sig, round_digits=2)
    sd = sig * math.sqrt(pinrun.var_factor(r, [1.0]))
    f_hand = pinrun.ND.cdf((mu - (K_far - 0.005)) / sd)
    ck(f is not None and abs(f - f_hand) < 1e-12,
       "fair() on the tape-fed IndexWS equals Phi((mu-K+0.005)/sd) computed by hand (%.8f)" % (f or -1))
    sd = sig * math.sqrt(pinrun.var_factor(r, [1.0]))
    K_1sd = round(mu - sd, 2)                          # an interior value, not a saturated 1.0
    f_1sd = pinrun.fair(idx, IID, close, now_s, K_1sd, sig, round_digits=2)
    f_1sd_hand = pinrun.ND.cdf((mu - (K_1sd - 0.005)) / sd)
    ck(f_1sd is not None and abs(f_1sd - f_1sd_hand) < 1e-9 and 0.8 < f_1sd < 0.9,
       "and at one sd below the projection: %.6f by fair(), %.6f by hand" % (f_1sd or -1, f_1sd_hand))
    K_mid = round(mu, 2)
    f_mid = pinrun.fair(idx, IID, close, now_s, K_mid, sig, round_digits=2)
    ck(f_mid is not None and 0.2 < f_mid < 0.8, "a strike at the projection gives ~50%% (%.3f)" % (f_mid or -1))

    moves = idx.recent_moves(IID, pinrun.JUMP_LOOKBACK)
    # -- 4. planted books -> known decisions
    bids = [(0.95, 40.0)]
    asks = [(0.97, 50.0)]
    px, sz = side_ask(bids, asks, "yes")
    w, e, ev, ref = decide(f, px, sz, 25, poly_fee(px), K_far, spot, sig, moves)
    ck(w == "yes" and ref == [] and abs(e - ((f - 0.97) - poly_fee(0.97))) < 1e-12,
       "sure Up, 97c offer, 25 s left -> BUY Up, edge %.2fc after fee" % (100 * (e or 0)))
    w, e, ev, ref = decide(f, 0.99, 50.0, 25, poly_fee(0.99), K_far, spot, sig, moves)
    ck(w == "yes" and "price_ceiling" in ref and "ev_floor" in ref, "99c -> refused: price ceiling and EV floor")
    w, e, ev, ref = decide(f, 0.94, 50.0, 40, poly_fee(0.94), K_far, spot, sig, moves)
    ck("early_min_price" in ref, "94c with 40 s left -> refused by the early-leg 95c floor")
    w, e, ev, ref = decide(f, 0.88, 50.0, 25, poly_fee(0.88), K_far, spot, sig, moves)
    ck(ref == ["edge_cap"], "88c with 25 s left -> only the 10c edge cap refuses (%s)" % ref)
    w, e, ev, ref = decide(f, 0.88, 50.0, 15, poly_fee(0.88), K_far, spot, sig, moves)
    ck(ref == [], "88c with 15 s left -> BUY (the cap only applies above 20 s)")
    w, e, ev, ref = decide(f, 0.80, 50.0, 15, poly_fee(0.80), K_far, spot, sig, moves)
    ck("dump_guard" in ref, "80c on a certainty -> dump guard")
    w, e, ev, ref = decide(f, 0.97, 50.0, 50, poly_fee(0.97), K_far, spot, sig, moves)
    ck("tau" in ref, "50 s left -> outside the 45 s window")
    # Down side: projection far BELOW the strike, Down ask = 1 - Up bid
    K_hi = round(mu + 200.0, 2)
    f_lo = pinrun.fair(idx, IID, close, now_s, K_hi, sig, round_digits=2)
    px, sz = side_ask([(0.03, 25.0)], [(0.05, 10.0)], "no")
    w, e, ev, ref = decide(f_lo, px, sz, 25, poly_fee(px), K_hi, spot, sig, moves)
    ck(w == "no" and px == 0.97 and sz == 25.0 and ref == [],
       "sure Down, Up bid 3c -> Down ask 97c x 25 -> BUY Down")

    # -- 5. NULL world: strike at the projection every second -> never buys
    buys = 0
    for t in range(close - 45, close - 25 + 1):
        pr = pinrun.projection(idx, IID, close, t)
        if pr is None:
            continue
        Kn = round(pr[0], 2)
        fn = pinrun.fair(idx, IID, close, t, Kn, sig, round_digits=2)
        for pxn in (0.50, 0.90, 0.97):
            wn, en, evn, rn = decide(fn, pxn, 100.0, close - t, poly_fee(pxn), Kn, spot, sig, moves)
            buys += (wn is not None and not rn)
    ck(buys == 0, "null world (strike = projection): 0 buys over 21 seconds x 3 prices")

    # -- 6. the incremental gzip tail on a planted, growing file
    import tempfile
    tmp = tempfile.mkdtemp(prefix="polypaper_st_")
    p = os.path.join(tmp, "x.jsonl.gz")
    fh = open(p, "wb")
    gz = gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=4)
    gz.write(b'{"a":1}\n{"a":2}\n{"a":')
    gz.flush()
    fh.flush()
    t = GzTail(p)
    l1 = t.poll()
    gz.write(b'3}\n')
    gz.flush()
    fh.flush()
    l2 = t.poll()
    gz.close()
    fh.close()
    with open(p, "ab") as fh2:                 # a second gzip member
        fh2.write(gzip.compress(b'{"a":4}\n'))
    l3 = t.poll()
    ck(l1 == ['{"a":1}', '{"a":2}'] and l2 == ['{"a":3}'] and l3 == ['{"a":4}'],
       "the gzip tail returns only complete lines, resumes mid-line, and crosses members (%s %s %s)" % (l1, l2, l3))
    with open(p, "rb") as fh3:
        data = fh3.read()
    p2 = os.path.join(tmp, "torn.jsonl.gz")
    with open(p2, "wb") as fh4:
        fh4.write(data[: len(data) // 2])
    t2 = GzTail(p2)
    l4 = t2.poll()
    ck(t2.errors == 0 and all(x.startswith('{"a":') for x in l4), "a torn file yields its readable prefix, no error")
    for fn in (p, p2):
        os.remove(fn)
    os.rmdir(tmp)

    # -- 7. a whole window, offline: planted tape files + planted book + fake GET
    tmp = tempfile.mkdtemp(prefix="polypaper_st2_")
    for chan in ("cfbenchmarks_value", "ticker"):
        os.makedirs(os.path.join(tmp, chan))
    start = close - 900
    K_plant = round(mu - 200.0, 2)

    def cf_line(s, v):
        return json.dumps({"type": "cfbenchmarks_value", "msg": {"index_id": IID, "data": json.dumps(
            {"type": "value", "time": s * 1000, "id": IID, "value": "%.2f" % v})}, "_rx_ms": s * 1000 + 100})
    byhour = {}
    for s in range(close - 1200, close + 5):
        v = vals.get(s, vals[close - 25])
        byhour.setdefault(s // 3600, []).append(cf_line(s, v))
    for s in range(close - 60, close + 5):
        byhour.setdefault(s // 3600, []).append(json.dumps({"type": "ticker", "msg": {
            "market_ticker": kalshi_prefix(close) + "00", "yes_bid_dollars": "0.9500", "yes_bid_size_fp": "9.00",
            "yes_ask_dollars": "0.9600", "yes_ask_size_fp": "30.00"}, "_rx_ms": s * 1000 + 200}))
    for h, ls in byhour.items():
        cf = [x for x in ls if '"cfbenchmarks_value"' in x]
        tk = [x for x in ls if '"ticker"' in x]
        name = time.strftime("%Y%m%dT%H", time.gmtime(h * 3600)) + ".jsonl.gz"
        for chan, rows in (("cfbenchmarks_value", cf), ("ticker", tk)):
            with gzip.open(os.path.join(tmp, chan, name), "wt", encoding="utf-8") as g:
                g.write("\n".join(rows) + "\n")
    settle_true = round(sum(vals.get(s, vals[close - 25]) for s in range(close - 60, close)) / 60.0, 2)

    def fake_get(path, q):
        return 200, {"market": {"assetPriceTerms": {"priceToBeat": {"value": "%.2f" % K_plant},
                                                    "settlementPrice": {"value": "%.2f" % settle_true}}}}
    logp = os.path.join(tmp, "log.jsonl")
    bot = Bot(logp, windows=1, minutes=5, size=10, get_fn=fake_get)
    bot.tape.tape = tmp
    bot.tape.tails.clear()
    bot.books[slug_for(start)] = (0.0, [(0.95, 40.0)], [(0.97, 50.0)])
    for t_ in range(close - 30, close + 3):
        bot.books[slug_for(start)] = (t_ + 0.1, [(0.95, 40.0)], [(0.97, 50.0)])
        bot.step(t_ + 0.35)
    recs = [json.loads(x) for x in open(logp, encoding="utf-8")]
    secs = [x for x in recs if x["type"] == "sec"]
    pbuys = [x for x in recs if x["type"] == "paper_buy" and x["venue"] == "polymarket"]
    kbuys = [x for x in recs if x["type"] == "paper_buy" and x["venue"] == "kalshi"]
    stl = [x for x in recs if x["type"] == "settle"]
    ck(len(secs) == 30, "one record per second from tau 30 to tau 1 (%d)" % len(secs))
    ck(len(pbuys) == 1 and pbuys[0]["price"] == 0.97 and pbuys[0]["n"] == 10 and pbuys[0]["tau"] == 30,
       "exactly one Polymarket paper entry, 10 @ 97c at the first eligible second")
    ck(len(kbuys) == 1 and kbuys[0]["price"] == 0.96,
       "the Kalshi comparison reads the planted ticker tape at the same second (96c)")
    ck(all(x["k_ask"] == 0.96 for x in secs if x["tau"] <= 30),
       "Kalshi same-second ask present on every second")
    ck(len(stl) == 1 and stl[0]["up"] is True and stl[0]["p_pnl"] == 0.28 and stl[0]["poly_settle"] == settle_true,
       "settles Up from Polymarket's settlement price; paper P&L +$0.28 (%s)" % (stl[0] if stl else None))
    ck(bot.done, "the one-window run stops itself after the settle")
    buf = []
    report([logp], out=buf.append)
    ck(any("P&L $+0.28" in x for x in buf), "--report reproduces the paper P&L")
    for root, dirs, files in os.walk(tmp, topdown=False):
        for fn in files:
            os.remove(os.path.join(root, fn))
        for dn in dirs:
            os.rmdir(os.path.join(root, dn))
    os.rmdir(tmp)

    # -- 8. read-only by construction (needles assembled so this test cannot match itself)
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[:src.rindex("\ndef selftest():")]
    ck(("PO" + "ST") not in body and ("create" + "-order") not in body and ("portfolio/" + "orders") not in body,
       "READ-ONLY: no order route and no writing verb in the working code")
    ck(body.count('open(self.path, "rb")') == 1 and "kalshi_data" in body,
       "the tape is opened 'rb' only")
    print("polypaper selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--report", nargs="*")
    ap.add_argument("--windows", type=int, default=None, help="stop after this many settled windows")
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--size", type=float, default=PAPER_SIZE)
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    if a.report is not None:
        report(a.report or None)
        return 0
    if os.environ.get("KALS_SELFTESTED") != "1" or a.selftest:
        if not selftest():
            return 1
        if a.selftest:
            return 0
    if os.path.exists(STOP):
        print("stop file present:", STOP)
        return 0
    log = a.log or os.path.join(RESULTS, "polypaper-%s.jsonl" % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    print("polypaper: logging to", log, flush=True)
    bot = Bot(log, windows=a.windows, minutes=a.minutes, size=a.size)
    asyncio.run(bot.main())
    report([log])
    return 0


if __name__ == "__main__":
    sys.exit(main())
