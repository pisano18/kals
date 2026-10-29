#!/usr/bin/env python3
r"""jumpband_live.py -- the slow-coin JUMP-BAND buyer on the 15-minute crypto markets. PAPER ARM, read-only.

PURPOSE
  Run IDEA_LEDGER LS25 (VIABLE on a 42-day book replay, write-up in the jumpband scratch folder's VERDICT.md) as a
  paper bot: watch the index prints and the live order books, log every buy the rule WOULD make and what it would
  have earned, so the paper record can be judged against the replay (+6.6c a contract, about 11 buys a day, kill
  rule: under +3c a contract or a negative half on the first 150 buys). It places NO orders. The --live flag exists
  only as a stub that refuses to run.

THE RULE (definitions copied from scan.py / analyze.py of the replay)
  Markets  the 15-minute crypto series KXBNB15M, KXHYPE15M, KXZEC15M, KXNEAR15M (--series). The fast coins
           BTC/ETH/SOL/XRP/DOGE are added only with --fast-k 4: for them the trigger is k >= 4 and the band 70-95c.
  Index    Kalshi's websocket channel cfbenchmarks_value: one print a second per index. For each coin keep the
           trailing 300 one-second slots of print changes (a slot is empty when either second is missing, so a
           reconnect gap counts nothing); the sd is the sample sd over the valid changes, at least 150 of them,
           and excludes the current change.
  Trigger  a one-second print move of at least K x that sd (K = 2.0, --k) with 10 <= tau <= 60 s to the close,
           tau = close second - print second. Never inside the last 10 s, never beyond 60 s.
  Side     the side the jump favours: price up -> YES, price down -> NO (every 15M strike is a
           'greater_or_equal' line; settlement = mean of the 60 one-second prints before the close vs the strike).
           The projected settlement side is logged, not used (the replay found no gain in requiring it).
  Book     the live book is rebuilt from orderbook_snapshot + orderbook_delta (the ticker channel is throttled
           and misses half the asks, so it is NOT used). Act when the favoured side's best ask is in
           [--lo, --hi] = [0.70, 0.90]: a would-be IOC buy at the seen ask for everything offered at or below it,
           up to --max-contracts (100). One buy per market, held to settlement.
  Fee      0.07 x price x (1 - price) per contract, rounded UP to the cent per order.
  Settle   paper: the result is computed from the 60 prints held AND confirmed from the market_lifecycle_v2
           'determined' message; both are logged, the lifecycle result wins when they differ. If no lifecycle
           message arrives within SETTLE_WAIT s of the close the computed result is booked and a later lifecycle
           message corrects it. (A live arm would also read /markets/<ticker>; not built.)

MODES
  default  paper. The only secret needed is the key for the websocket handshake and the signed discovery GETs
           (research/kauth.py). Every would-be buy is logged as kind "paper_buy", every result as "paper_settle".
  --live   STUB: raises SystemExit("live order path not built") before anything could be sent.

FLAGS
  --series A,B,...      series to watch (default the four slow coins)
  --k 2.0               trigger size in trailing sds (slow coins)
  --lo 0.70 --hi 0.90   ask band for the slow coins
  --fast-k 4            also watch BTC/ETH/SOL/XRP/DOGE with k >= this and band 70-95c (off by default)
  --max-contracts 100   cap per paper buy
  --minutes 20160       run length (default 14 days)
  --log PATH            default C:\kals-repo\results\jumpband-paper.jsonl
  --selftest            offline self-test (fake prints, fake book, fake lifecycle); exit 0 on PASS

LOG (JSON lines)  start, market, strike, ws_up, ws_down, ws_subscribe, ws_subscribed, ws_error, seq_gap, trigger
  (every qualifying jump with the ask seen and the outcome), paper_buy, paper_settle, lifecycle_late,
  settle_corrected, market_done, health (every 5 min), stop_file, exit.
STOP   create C:\kals-repo\results\jumpband-paper.stop; the run logs stop_file and exit, then ends.

START IN PAPER ON THE SERVER (from C:\kals-repo):
    C:\Python314\python.exe research\cleanroom\jumpband_live.py --selftest
    C:\Python314\python.exe research\cleanroom\jumpband_live.py --minutes 20160
"""
import argparse
import asyncio
import collections
import json
import math
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

SLOW = ("KXBNB15M", "KXHYPE15M", "KXZEC15M", "KXNEAR15M")
FAST = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M")
INDEX = {"KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI", "KXXRP15M": "XRPUSD_RTI",
         "KXDOGE15M": "DOGEUSD_RTI", "KXBNB15M": "BNBUSD_RTI", "KXHYPE15M": "HYPEUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
         "KXNEAR15M": "NEARUSD_RTI"}
ROUND_DIGITS = {"KXBTC15M": 2, "KXETH15M": 2, "KXSOL15M": 4, "KXXRP15M": 4, "KXDOGE15M": 7, "KXHYPE15M": 4,
                "KXBNB15M": 2, "KXZEC15M": 4, "KXNEAR15M": 4}          # fallback when Kalshi sends none
RESULTS = r"C:\kals-repo\results"
LOG = os.path.join(RESULTS, "jumpband-paper.jsonl")
STOP_FILE = os.path.join(RESULTS, "jumpband-paper.stop")
WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
WS_PATH = "/trade-api/ws/v2"

K = 2.0
LO = 0.70
HI = 0.90
FAST_LO = 0.70
FAST_HI = 0.95
MAX_CONTRACTS = 100.0
TAU_LO = 10
TAU_HI = 60
SIGW = 300                   # trailing window, one slot per second
SIGMIN = 150                 # valid changes needed before the sd counts
MAX_LAG = 3.0                # a print older than this by the wall clock is not acted on (a replayed burst after a reconnect)
SETTLE_WAIT = 120.0          # seconds after the close before the computed result is booked without a lifecycle message
FORGET_S = 1200.0            # drop a market this long after its close
WATCH_AHEAD = 1200.0         # discover markets closing within this many seconds


# ---------------------------------------------------------------------------------------------------- helpers
def fee(n, px):
    """Kalshi taker fee in dollars for n contracts at px, rounded up to the cent per order (analyze.py)."""
    if n <= 0:
        return 0.0
    return math.ceil(0.07 * px * (1 - px) * n * 100 - 1e-9) / 100.0


def parse_iso(s):
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def rss_mb():
    try:
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), wt.DWORD]
        if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return None
        return round(pmc.WorkingSetSize / 1e6, 1)
    except Exception:
        return None


class Logger:
    def __init__(self, path=None, sink=None, now=None):
        self.path, self.sink, self.now = path, sink, now
        self.lock = threading.Lock()

    def write(self, kind, **kw):
        t = self.now() if self.now else time.time()
        rec = {"t": iso(t), "kind": kind}
        rec.update(kw)
        line = json.dumps(rec, default=str)
        with self.lock:
            if self.sink is not None:
                self.sink.append(rec)
            if self.path:
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")


# ---------------------------------------------------------------------------------------------------- the index sd
class Sigma:
    """scan.py's sig_series, kept live: one slot per second holding the one-second change (None when the second
    before is missing), the last SIGW slots; sd = sample sd over the valid changes, None under SIGMIN of them.
    Call sd() BEFORE push(): the sd a print is judged against ends at the second before it."""

    def __init__(self):
        self.q = collections.deque()
        self.s1 = self.s2 = 0.0
        self.n = 0
        self.last_sec = None
        self.last_v = None

    def sd(self):
        if self.n < SIGMIN:
            return None
        mu = self.s1 / self.n
        var = (self.s2 - self.n * mu * mu) / (self.n - 1)
        return math.sqrt(var) if var > 0 else None

    def _slot(self, d):
        self.q.append(d)
        if d is not None:
            self.s1 += d; self.s2 += d * d; self.n += 1
        if len(self.q) > SIGW:
            o = self.q.popleft()
            if o is not None:
                self.s1 -= o; self.s2 -= o * o; self.n -= 1

    def push(self, sec, v):
        """Returns the change from the second before (None after a gap), or the string 'dup' for an old print."""
        if self.last_sec is not None:
            if sec <= self.last_sec:
                return "dup"
            for _ in range(min(sec - self.last_sec - 1, SIGW)):     # the missing seconds hold nothing
                self._slot(None)
            d = (v - self.last_v) if sec == self.last_sec + 1 else None
        else:
            d = None
        self._slot(d)
        self.last_sec, self.last_v = sec, v
        return d


# ---------------------------------------------------------------------------------------------------- book
class Book:
    """Resting bids per side (fxtake_live.Book); the ask for a side is 1 - the other side's best bid."""

    def __init__(self):
        self.yes, self.no = {}, {}
        self.synced = False
        self.last_msg = None

    def snapshot(self, msg, t):
        self.yes, self.no = {}, {}
        for side, d in (("yes", self.yes), ("no", self.no)):
            for a, b in (msg.get(side + "_dollars_fp") or msg.get(side + "_dollars") or []):
                d[round(float(a), 4)] = float(b)
            for a, b in (msg.get(side) or []):                      # cents form, if ever sent
                d[round(float(a) / 100.0, 4)] = float(b)
        self.synced, self.last_msg = True, t

    def delta(self, msg, t):
        d = self.yes if msg.get("side") == "yes" else self.no
        px = round(float(msg["price_dollars"]), 4)
        d[px] = d.get(px, 0.0) + float(msg["delta_fp"])
        if d[px] <= 1e-9:
            d.pop(px, None)
        self.last_msg = t

    def best_bid(self, side):
        d = self.yes if side == "yes" else self.no
        return max(d) if d else None

    def asks(self, side):
        """[(ask px ascending, qty)] for buying `side`, from the other side's bids."""
        d = self.no if side == "yes" else self.yes
        return sorted((round(1 - p, 4), q) for p, q in d.items() if q > 1e-9)


# ---------------------------------------------------------------------------------------------------- the rule
class Trader:
    """Prints in, books in, paper buys and paper settles out. Pure: no network, the clock is injected."""

    def __init__(self, log, live=False, now=time.time, k=K, lo=LO, hi=HI, max_contracts=MAX_CONTRACTS, fast_k=None):
        self.log, self.live, self.now = log, live, now
        self.k, self.lo, self.hi, self.max_contracts, self.fast_k = float(k), float(lo), float(hi), float(max_contracts), fast_k
        self.markets = {}        # ticker -> {"close_s","series","index","strike","rd","strike_src","triggers","inband","done"}
        self.books = {}          # ticker -> Book
        self.sig = {}            # index_id -> Sigma
        self.prints = {}         # index_id -> {sec: value} for the last ~8 minutes
        self.bought = set()      # one buy per market, ever
        self.held = {}           # ticker -> the paper position
        self.n_prints = collections.Counter()
        self.prints_since = now()
        self.n_triggers = self.n_buys = self.n_settled = self.n_lost = 0
        self.run_pnl = 0.0
        self.stopped = False

    # --- rule parameters per series ---
    def rule_for(self, series):
        if series in FAST:
            return float(self.fast_k), FAST_LO, FAST_HI
        return self.k, self.lo, self.hi

    # --- markets ---
    def add_market(self, tk, series, close_s, strike=None, rd=None, strike_src=None):
        m = self.markets.get(tk)
        if m is None:
            if series in FAST and self.fast_k is None:
                return
            m = {"close_s": float(close_s), "series": series, "index": INDEX.get(series), "strike": None, "rd": None,
                 "strike_src": None, "triggers": 0, "inband": 0, "done": False}
            self.markets[tk] = m
            self.books[tk] = Book()
            self.log.write("market", ticker=tk, series=series, close_s=close_s, close=iso(close_s), rule=self.rule_for(series))
        if strike is not None and (m["strike"] != float(strike) or m["rd"] != rd):
            m["strike"], m["rd"], m["strike_src"] = float(strike), rd, strike_src
            self.log.write("strike", ticker=tk, strike=m["strike"], round_digits=rd, src=strike_src)

    def on_snapshot(self, tk, msg, now):
        b = self.books.get(tk)
        if b is not None:
            b.snapshot(msg, now)

    def on_delta(self, tk, msg, now):
        b = self.books.get(tk)
        if b is not None and b.synced:
            b.delta(msg, now)

    def unsync(self):
        for b in self.books.values():
            b.synced = False

    # --- prints and the decision ---
    def on_print(self, iid, sec, value, now, sending_ms=None):
        sg = self.sig.get(iid)
        if sg is None:
            sg = self.sig[iid] = Sigma()
        sd = sg.sd()                                              # over the changes ending at sec - 1
        d = sg.push(sec, value)
        if d == "dup":
            return
        pr = self.prints.get(iid)
        if pr is None:
            pr = self.prints[iid] = {}
        pr[sec] = value
        if len(pr) > 600:
            for s in [s for s in pr if s < sec - 480]:
                del pr[s]
        self.n_prints[iid] += 1
        if d is None or not sd:
            return
        dz = d / sd
        for tk, m in self.markets.items():
            if m["index"] != iid:
                continue
            tau = int(round(m["close_s"])) - sec
            if not (TAU_LO <= tau <= TAU_HI):
                continue
            k, lo, hi = self.rule_for(m["series"])
            if abs(dz) < k:
                continue
            m["triggers"] += 1
            self.n_triggers += 1
            side = "yes" if dz > 0 else "no"
            b = self.books.get(tk)
            ask, size = None, 0.0
            if b is not None and b.synced:
                asks = b.asks(side)
                if asks:
                    ask, size = asks[0]
            proj, pside = self.projection(m, pr, sec, value)
            rec = {"ticker": tk, "side": side, "tau": tau, "print_move_sd": round(dz, 3), "sigma": sd, "move": round(d, 8),
                   "value": value, "sec": sec, "lag_s": round(now - sec, 3), "k": k, "band": [lo, hi], "ask": ask,
                   "ask_size": size, "proj": proj, "pside": pside, "strike": m["strike"]}
            if tk in self.bought:
                why = "already_bought"
            elif b is None or not b.synced:
                why = "no_book"
            elif ask is None:
                why = "no_ask"
            elif now - sec > MAX_LAG:
                why = "stale_print"
            elif not (lo - 1e-9 <= ask <= hi + 1e-9):
                why = "out_of_band"
            elif self.stopped:
                why = "stopped"
            else:
                why = None
            if why is None or why == "stopped":
                m["inband"] += 1
            self.log.write("trigger", outcome=why or "buy", **rec)
            if why is None:
                self.place(tk, side, ask, size, rec, sending_ms)

    def projection(self, m, pr, sec, value):
        """scan.py's proj / pside: the settlement average if the index stayed here, and the side it gives."""
        if m["strike"] is None:
            return None, None
        C = int(round(m["close_s"]))
        locked = [pr.get(s) for s in range(C - 60, sec + 1)]
        locked = [x for x in locked if x is not None]
        if sec < C - 60:
            proj = value
        else:
            proj = (sum(locked) + (60 - len(locked)) * value) / 60.0
        rd = m["rd"]
        keff = m["strike"] - (0.5 * 10 ** (-rd) if rd is not None else 0.0)
        return round(proj, 8), ("yes" if proj >= keff else "no")

    def place(self, tk, side, ask, size, rec, sending_ms=None):
        """The would-be IOC at the seen ask for everything at or below it (= the best level), capped."""
        qty = round(min(size, self.max_contracts), 2)
        if qty <= 0:
            return
        cost = round(qty * ask, 4)
        f = fee(qty, ask)
        if self.live:
            raise SystemExit("live order path not built")
        m = self.markets[tk]
        self.bought.add(tk)
        self.held[tk] = {"side": side, "qty": qty, "px": ask, "cost": cost, "fee": f, "close_s": m["close_s"],
                         "settled": False, "result": None, "pnl": None, "src": None}
        self.n_buys += 1
        self.log.write("paper_buy", ticker=tk, series=m["series"], side=side, tau=rec["tau"], print_move_sd=rec["print_move_sd"],
                       sigma=rec["sigma"], move=rec["move"], value=rec["value"], sec=rec["sec"], ask=ask, ask_size=size, qty=qty,
                       cost=cost, fee=f, lag_s=rec["lag_s"], sending_ts_ms=sending_ms, k=rec["k"], band=rec["band"],
                       strike=m["strike"], proj=rec["proj"], pside=rec["pside"])

    # --- settlement ---
    def calc_result(self, tk):
        """(result, average, prints held) from the 60 one-second prints before the close; result None unless all
        60 are held and the strike is known. Rounding as scan.py: round(avg, rd) >= strike -> yes."""
        m = self.markets.get(tk)
        if m is None:
            return None, None, 0
        C = int(round(m["close_s"]))
        pr = self.prints.get(m["index"], {})
        xs = [pr.get(s) for s in range(C - 60, C)]
        have = [x for x in xs if x is not None]
        if not have:
            return None, None, 0
        avg = sum(have) / len(have)
        if len(have) < 60 or m["strike"] is None:
            return None, round(avg, 8), len(have)
        rd = m["rd"]
        r = round(avg, rd) if rd is not None else avg
        return ("yes" if r >= m["strike"] else "no"), round(avg, 8), len(have)

    def _book_settle(self, tk, result, calc, life, avg, n, src):
        v = self.held[tk]
        m = self.markets.get(tk, {})
        won = v["side"] == result
        pnl = (v["qty"] * (1 - v["px"]) - v["fee"]) if won else (-v["qty"] * v["px"] - v["fee"])
        pnl = round(pnl, 4)
        v.update(settled=True, result=result, pnl=pnl, src=src, won=won)
        self.run_pnl = round(self.run_pnl + pnl, 4)
        self.n_settled += 1
        self.n_lost += 0 if won else 1
        self.log.write("paper_settle", ticker=tk, side=v["side"], qty=v["qty"], price=v["px"], cost=v["cost"], fee=v["fee"],
                       result=result, result_calc=calc, result_lifecycle=life, agree=(None if calc is None or life is None else calc == life),
                       avg60=avg, n_prints=n, strike=m.get("strike"), round_digits=m.get("rd"), won=won, pnl=pnl,
                       run_pnl=self.run_pnl, src=src, settled=self.n_settled, lost=self.n_lost)

    def on_lifecycle(self, msg, now):
        tk = msg.get("market_ticker")
        if tk not in self.markets:
            return
        et = msg.get("event_type")
        if et == "metadata_updated" and msg.get("floor_strike") is not None:
            cs = msg.get("custom_strike") or {}
            rd = cs.get("round_digits")
            m = self.markets[tk]
            self.add_market(tk, m["series"], m["close_s"], float(msg["floor_strike"]),
                            int(rd) if rd is not None else ROUND_DIGITS.get(m["series"]), "lifecycle")
        elif et == "determined" and msg.get("result") in ("yes", "no"):
            life = msg["result"]
            v = self.held.get(tk)
            if v is None:
                return
            calc, avg, n = self.calc_result(tk)
            if not v["settled"]:
                self._book_settle(tk, life, calc, life, avg, n, "lifecycle")
                return
            # already booked from the prints: confirm, and correct if Kalshi disagrees
            agree = v["result"] == life
            self.log.write("lifecycle_late", ticker=tk, result_lifecycle=life, result_booked=v["result"], agree=agree)
            if not agree:
                old = v["pnl"]
                won = v["side"] == life
                pnl = round((v["qty"] * (1 - v["px"]) - v["fee"]) if won else (-v["qty"] * v["px"] - v["fee"]), 4)
                self.run_pnl = round(self.run_pnl + pnl - old, 4)
                self.n_lost += (0 if won else 1) - (0 if v.get("won") else 1)
                v.update(result=life, pnl=pnl, src="lifecycle_corrected", won=won)
                self.log.write("settle_corrected", ticker=tk, result=life, pnl=pnl, old_pnl=old, run_pnl=self.run_pnl)

    def settle_due(self, now):
        """Book from the prints when no lifecycle message came within SETTLE_WAIT of the close; per-market summary
        once the close has passed; forget old markets."""
        for tk, v in list(self.held.items()):
            if v["settled"] or now < v["close_s"] + SETTLE_WAIT:
                continue
            calc, avg, n = self.calc_result(tk)
            if calc is not None:
                self._book_settle(tk, calc, calc, None, avg, n, "calc")
            elif now >= v["close_s"] + FORGET_S:
                v.update(settled=True, src="unsettled")
                self.log.write("unsettled", ticker=tk, n_prints=n, strike=self.markets.get(tk, {}).get("strike"))
            elif not v.get("pending_logged"):
                v["pending_logged"] = True
                self.log.write("settle_pending", ticker=tk, n_prints=n, strike=self.markets.get(tk, {}).get("strike"))
        for tk, m in list(self.markets.items()):
            if not m["done"] and now >= m["close_s"] + 2:
                m["done"] = True
                b = self.books.get(tk)
                self.log.write("market_done", ticker=tk, triggers=m["triggers"], inband=m["inband"], bought=tk in self.bought,
                               strike=m["strike"], book_synced=bool(b and b.synced))
            if m["close_s"] < now - FORGET_S and (tk not in self.held or self.held[tk]["settled"]):
                self.markets.pop(tk, None); self.books.pop(tk, None); self.bought.discard(tk); self.held.pop(tk, None)

    # --- stop and health ---
    def check_stop_file(self):
        if not self.stopped and os.path.exists(STOP_FILE):
            self.stopped = True
            self.log.write("stop_file", path=STOP_FILE)
        return self.stopped

    def health(self, **extra):
        now = self.now()
        el = max(now - self.prints_since, 1e-9)
        pps = {iid: round(n / el, 3) for iid, n in sorted(self.n_prints.items())}
        self.n_prints = collections.Counter(); self.prints_since = now
        sds = {iid: (None if s.sd() is None else round(s.sd(), 6)) for iid, s in sorted(self.sig.items())}
        self.log.write("health", markets=len(self.markets), books_synced=sum(1 for b in self.books.values() if b.synced),
                       prints_per_s=pps, sigma=sds, triggers=self.n_triggers, paper_buys=self.n_buys,
                       open_positions=sum(1 for v in self.held.values() if not v["settled"]), settled=self.n_settled,
                       lost=self.n_lost, paper_pnl=self.run_pnl, stopped=self.stopped, rss_mb=rss_mb(), **extra)


# ---------------------------------------------------------------------------------------------------- frames
def handle_frame(tr, obj, now, ws_state, log):
    """One parsed websocket frame -> the trader. The live feed and the self-test both come through here."""
    t = obj.get("type")
    msg = obj.get("msg") or {}
    if t == "cfbenchmarks_value":
        try:
            data = msg.get("data")
            data = json.loads(data) if isinstance(data, str) else (data or {})
            tm = int(data["time"])
            if tm % 1000:
                return
            tr.on_print(msg["index_id"], tm // 1000, float(data["value"]), now, obj.get("sending_ts_ms"))
        except (KeyError, TypeError, ValueError) as e:
            log.write("bad_print", err=repr(e)[:120])
    elif t == "orderbook_delta":
        sid, seq = obj.get("sid"), obj.get("seq")
        exp = ws_state["seq"].get(sid)
        if exp is not None and seq is not None and seq != exp + 1:
            log.write("seq_gap", sid=sid, expected=exp + 1, got=seq)
            tr.unsync()
            ws_state["resync"] = True
        if seq is not None:
            ws_state["seq"][sid] = seq
        tr.on_delta(msg.get("market_ticker"), msg, now)
    elif t == "orderbook_snapshot":
        if obj.get("seq") is not None:
            ws_state["seq"][obj.get("sid")] = obj.get("seq")
        tr.on_snapshot(msg.get("market_ticker"), msg, now)
    elif t == "market_lifecycle_v2":
        tr.on_lifecycle(msg, now)
    elif t == "subscribed":
        ws_state["sids"][msg.get("sid")] = msg.get("channel")
        log.write("ws_subscribed", id=obj.get("id"), sid=msg.get("sid"), channel=msg.get("channel"))
    elif t == "error":
        log.write("ws_error", msg=str(obj)[:300])
        if msg.get("code") == 25:                                 # subscription buffer overflow: resubscribe everything
            tr.unsync()
            ws_state["resync"] = True


def new_ws_state():
    return {"ws": None, "next_id": 1, "sids": {}, "seq": {}, "subscribed": set(), "resync": False}


# ---------------------------------------------------------------------------------------------------- live plumbing
def market_from_rest(mk, series, doge_prev=None):
    """(ticker, close_s, strike, round_digits, src) from one /markets row. DOGE's floor_strike is truncated to 6 dp,
    so the previous market's expiration_value is the exact strike (bettor_paper.py)."""
    tk = mk["ticker"]
    close_s = parse_iso(mk["close_time"])
    cs = mk.get("custom_strike") or {}
    rd = cs.get("round_digits")
    rd = int(rd) if rd not in (None, "") else ROUND_DIGITS.get(series)
    strike, src = None, None
    if cs.get("floor_strike") not in (None, ""):
        strike, src = float(cs["floor_strike"]), "custom_strike"
    elif mk.get("floor_strike") is not None:
        strike, src = float(mk["floor_strike"]), "floor_strike"
    if series == "KXDOGE15M":
        for p in doge_prev or []:
            try:
                if parse_iso(p["close_time"]) == close_s - 900 and p.get("expiration_value"):
                    strike, src = float(str(p["expiration_value"]).replace(",", "")), "prev_expiration_value"
            except Exception:
                pass
    return tk, close_s, strike, rd, src


async def watch_stop(tr, end, log, period=0.5):
    """Ends the run when the stop file appears: the task returns, run_live cancels the rest."""
    while time.time() < end:
        if tr.check_stop_file():
            log.write("stopping", open_positions=sum(1 for v in tr.held.values() if not v["settled"]))
            return
        await asyncio.sleep(period)


async def run_live(tr, minutes, log, series):
    import websockets
    import kauth
    loop = asyncio.get_running_loop()
    end = time.time() + minutes * 60
    ws_state = new_ws_state()
    index_ids = sorted({INDEX[s] for s in series})

    def signed_get(path, params):
        st, d = kauth.get(path, params)
        if st == 429:
            time.sleep(3)
            st, d = kauth.get(path, params)
        return st, d

    async def discover():
        """Signed GET of the open markets per series, once a minute; markets closing within WATCH_AHEAD are watched."""
        while time.time() < end:
            doge_prev = []
            if "KXDOGE15M" in series:
                try:
                    st, d = await loop.run_in_executor(None, signed_get, "/markets", {"series_ticker": "KXDOGE15M", "status": "settled", "limit": 5})
                    doge_prev = (d.get("markets") or []) if st == 200 and isinstance(d, dict) else []
                except Exception as e:
                    log.write("discover_error", series="KXDOGE15M", err=repr(e)[:200])
            for s in series:
                try:
                    st, d = await loop.run_in_executor(None, signed_get, "/markets", {"series_ticker": s, "status": "open", "limit": 5})
                    if st != 200 or not isinstance(d, dict):
                        log.write("discover_error", series=s, status=st, err=str(d)[:120])
                        continue
                    for mk in d.get("markets") or []:
                        try:
                            tk, c, strike, rd, src = market_from_rest(mk, s, doge_prev)
                        except Exception as e:
                            log.write("bad_market", ticker=mk.get("ticker"), err=repr(e)[:160])
                            continue
                        if 0 < c - time.time() < WATCH_AHEAD:
                            tr.add_market(tk, s, c, strike, rd, src)
                except Exception as e:
                    log.write("discover_error", series=s, err=repr(e)[:200])
                await asyncio.sleep(1.0)
            await asyncio.sleep(55)

    async def subscribe_new(ws):
        want = [tk for tk in list(tr.markets) if tk not in ws_state["subscribed"]]
        if not want:
            return
        i = ws_state["next_id"]; ws_state["next_id"] += 1
        await ws.send(json.dumps({"id": i, "cmd": "subscribe", "params": {"channels": ["orderbook_delta"], "market_tickers": want}}))
        ws_state["subscribed"].update(want)
        log.write("ws_subscribe", id=i, markets=want)

    async def resync(ws):
        """After a sequence gap or an overflow: drop every book subscription and take fresh snapshots."""
        sids = [sid for sid, ch in ws_state["sids"].items() if ch == "orderbook_delta"]
        if sids:
            i = ws_state["next_id"]; ws_state["next_id"] += 1
            await ws.send(json.dumps({"id": i, "cmd": "unsubscribe", "params": {"sids": sids}}))
            for sid in sids:
                ws_state["sids"].pop(sid, None); ws_state["seq"].pop(sid, None)
        ws_state["subscribed"] = set()
        ws_state["resync"] = False
        log.write("ws_resync", dropped_sids=sids)
        await subscribe_new(ws)

    async def feed():
        while time.time() < end:
            try:
                hdrs = kauth.headers("GET", WS_PATH)
                async with websockets.connect(WS_URL, additional_headers=hdrs, ping_interval=20, ping_timeout=20, max_size=2 ** 24) as ws:
                    ws_state["ws"] = ws
                    ws_state["subscribed"] = set(); ws_state["sids"] = {}; ws_state["seq"] = {}; ws_state["resync"] = False
                    tr.unsync()
                    log.write("ws_up")
                    i = ws_state["next_id"]; ws_state["next_id"] += 1
                    await ws.send(json.dumps({"id": i, "cmd": "subscribe", "params": {"channels": ["cfbenchmarks_value"], "index_ids": index_ids}}))
                    i = ws_state["next_id"]; ws_state["next_id"] += 1
                    await ws.send(json.dumps({"id": i, "cmd": "subscribe", "params": {"channels": ["market_lifecycle_v2"]}}))
                    await subscribe_new(ws)
                    last_sub = time.time()
                    while time.time() < end:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            raw = None
                        if ws_state["resync"]:
                            await resync(ws); last_sub = time.time()
                        elif time.time() - last_sub > 5:
                            await subscribe_new(ws); last_sub = time.time()
                        if raw is None:
                            continue
                        try:
                            obj = json.loads(raw)
                        except ValueError:
                            continue
                        handle_frame(tr, obj, time.time(), ws_state, log)
            except Exception as e:
                log.write("ws_down", err=repr(e)[:200])
                tr.unsync()
                await asyncio.sleep(2)
        ws_state["ws"] = None

    async def settle():
        while time.time() < end:
            tr.settle_due(time.time())
            await asyncio.sleep(5)

    async def health():
        while time.time() < end:
            await asyncio.sleep(300)
            tr.health(ws_up=ws_state["ws"] is not None, subscribed=len(ws_state["subscribed"]))

    async def decide():
        await watch_stop(tr, end, log)

    tasks = [asyncio.create_task(c()) for c in (discover, feed, decide, settle, health)]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    for t in done:
        if not t.cancelled() and t.exception():
            log.write("task_error", err=repr(t.exception())[:300])


# ---------------------------------------------------------------------------------------------------- selftest
def selftest():
    """A fake world through the live code path (handle_frame -> Trader): prints, books, lifecycle, stop file."""
    fails = []
    n = [0]

    def ck(cond, what):
        n[0] += 1
        print(("  ok   " if cond else "  FAIL ") + what)
        if not cond:
            fails.append(what)

    IID = "BNBUSD_RTI"
    PATTERN = (0.10, -0.05, 0.03, -0.08, 0.06, -0.06)      # one-second changes; max 0.1 is about 1.4 sd, so no stray trigger

    def print_frame(sec, v, iid=IID):
        return {"type": "cfbenchmarks_value", "sid": 2, "seq": sec, "sending_ts_ms": sec * 1000 + 30,
                "msg": {"index_id": iid, "received_at": sec * 1000 + 25,
                        "data": json.dumps({"type": "value", "time": sec * 1000, "id": iid, "value": "%.6f" % v})}}

    def snap_frame(tk, yes_bids, no_bids, seq=1, sid=4):
        return {"type": "orderbook_snapshot", "sid": sid, "seq": seq,
                "msg": {"market_ticker": tk, "yes_dollars_fp": [["%.4f" % p, "%.2f" % q] for p, q in yes_bids],
                        "no_dollars_fp": [["%.4f" % p, "%.2f" % q] for p, q in no_bids]}}

    def delta_frame(tk, side, px, dq, seq, sid=4):
        return {"type": "orderbook_delta", "sid": sid, "seq": seq,
                "msg": {"market_ticker": tk, "price_dollars": "%.4f" % px, "delta_fp": "%.2f" % dq, "side": side, "ts_ms": 0}}

    class World:
        """One market on the BNB index, prints warmed up to the second before `s_jump`."""

        def __init__(self, tau, close=1793156400, live=False, k=K, lo=LO, hi=HI, base=745.30, strike=745.00,
                     yes_bids=((0.80, 50.0),), no_bids=((0.15, 40.0), (0.10, 100.0)), series="KXBNB15M", fast_k=None, gap_at=None):
            self.sent = []
            self.T = [0.0]
            self.log = Logger(sink=self.sent, now=lambda: self.T[0])
            self.tr = Trader(self.log, live=live, now=lambda: self.T[0], k=k, lo=lo, hi=hi, fast_k=fast_k)
            self.ws = new_ws_state()
            self.C = close
            self.iid = INDEX[series]
            self.tk = "%s-26OCT272300-00" % series
            self.tr.add_market(self.tk, series, self.C, strike, 2, "test")
            self.s_jump = self.C - tau
            self.v = base
            self.i = 0
            self.last_sec = None
            sec = self.s_jump - 400
            while sec < self.s_jump:
                if gap_at is not None and gap_at[0] <= sec < gap_at[1]:
                    sec += 1
                    continue
                self.feed(sec)
                sec += 1
            self.frame(snap_frame(self.tk, yes_bids, no_bids))

        def step(self):
            d = PATTERN[self.i % len(PATTERN)]; self.i += 1
            return d

        def frame(self, obj, lag=0.1):
            if obj["type"] == "cfbenchmarks_value":
                try:
                    self.T[0] = json.loads(obj["msg"]["data"])["time"] / 1000.0 + lag
                except (ValueError, KeyError, TypeError):
                    pass
            handle_frame(self.tr, obj, self.T[0], self.ws, self.log)

        def feed(self, sec, v=None, lag=0.1):
            """The next pattern print (or the given value) at second sec."""
            if v is None:
                if self.last_sec is not None and sec == self.last_sec + 1:
                    self.v = self.v + self.step()
                else:
                    self.v = self.v + self.step()        # after a gap the change is never counted anyway
            else:
                self.v = v
            self.last_sec = sec
            self.frame(print_frame(sec, self.v, self.iid), lag)

        def sd(self):
            return self.tr.sig[self.iid].sd()

        def jump(self, mult, lag=0.1, sec=None):
            sec = self.s_jump if sec is None else sec
            sd = self.sd()
            self.feed(sec, self.v + mult * sd, lag)
            return sd

        def recs(self, kind):
            return [r for r in self.sent if r["kind"] == kind]

    # (a) a 2.5-sd jump at tau 30, favoured YES ask 0.85 x 40 -> one paper_buy of 40 at 0.85, fee 1.43
    w = World(30)
    sd0 = w.tr.sig[IID].sd()
    ck(sd0 is not None and w.tr.sig[IID].n == SIGW, "warm-up: 300 valid one-second changes, sd %.5f" % (sd0 or 0))
    ck(w.tr.n_triggers == 0 and not w.recs("paper_buy"), "the warm-up pattern (max 1.4 sd) fires nothing")
    w.jump(2.5)
    buys = w.recs("paper_buy")
    ck(len(buys) == 1, "(a) one paper_buy")
    b = buys[0] if buys else {}
    ck(b.get("side") == "yes" and b.get("tau") == 30 and b.get("ask") == 0.85 and b.get("ask_size") == 40.0 and b.get("qty") == 40.0,
       "(a) YES, tau 30, ask 0.85 x 40, qty 40: %s" % {k_: b.get(k_) for k_ in ("side", "tau", "ask", "ask_size", "qty")})
    # fee = 0.07 x 0.85 x 0.15 = 0.008925 a contract; x 40 = 0.357, rounded up to the cent per order = 0.36
    # (the brief's "0.0357 x 40 = 1.428 -> 1.43" is the same formula with the decimal point one place off)
    FEE40 = fee(40, 0.85)
    ck(abs(b.get("cost", 0) - 34.0) < 1e-9 and abs(b.get("fee", 0) - 0.36) < 1e-9 and FEE40 == 0.36,
       "(a) cost 34.00, fee 0.07 x 0.85 x 0.15 x 40 = 0.357 rounded up to 0.36")
    ck(abs(b.get("print_move_sd", 0) - 2.5) < 1e-6 and abs(b.get("sigma", 0) - sd0) < 1e-12, "(a) the record carries dz 2.5 and the sd it was judged against")
    trig = w.recs("trigger")
    ck(len(trig) == 1 and trig[0]["outcome"] == "buy", "(a) exactly one trigger record, outcome buy")
    ck(b.get("pside") == "yes" and b.get("proj") is not None and b.get("strike") == 745.0, "(a) projected settlement side logged (yes, index above the strike)")
    # the NO side: price down -> buy NO at the NO ask (1 - best YES bid)
    wn = World(30, yes_bids=((0.15, 30.0),), no_bids=((0.60, 20.0),))
    wn.jump(-2.5)
    bn = wn.recs("paper_buy")
    ck(len(bn) == 1 and bn[0]["side"] == "no" and bn[0]["ask"] == 0.85 and bn[0]["qty"] == 30.0, "a 2.5-sd DROP buys NO at the NO ask 0.85 x 30")
    # cap: 250 offered -> 100
    wc = World(30, no_bids=((0.15, 250.0),))
    wc.jump(2.5)
    ck(wc.recs("paper_buy") and wc.recs("paper_buy")[0]["qty"] == 100.0 and wc.recs("paper_buy")[0]["ask_size"] == 250.0,
       "250 offered at the seen ask -> qty capped at 100")
    # below k: a 1.9-sd move fires nothing
    wk = World(30)
    wk.jump(1.9)
    ck(wk.tr.n_triggers == 0 and not wk.recs("paper_buy"), "a 1.9-sd move is not a trigger")
    # (b) tau 8 and tau 65
    w8 = World(8); w8.jump(2.5)
    ck(not w8.recs("paper_buy") and w8.tr.n_triggers == 0, "(b) the same jump at tau 8 -> no buy (inside the last 10 s)")
    w65 = World(65); w65.jump(2.5)
    ck(not w65.recs("paper_buy") and w65.tr.n_triggers == 0, "(b) the same jump at tau 65 -> no buy (beyond 60 s)")
    w10 = World(10); w10.jump(2.5)
    w60 = World(60); w60.jump(2.5)
    ck(len(w10.recs("paper_buy")) == 1 and len(w60.recs("paper_buy")) == 1, "the edges tau 10 and tau 60 are inside the window")
    # (c) ask 0.93 and ask 0.65
    w93 = World(30, no_bids=((0.07, 40.0),)); w93.jump(2.5)
    ck(not w93.recs("paper_buy") and w93.recs("trigger") and w93.recs("trigger")[0]["outcome"] == "out_of_band" and w93.recs("trigger")[0]["ask"] == 0.93,
       "(c) ask 0.93 -> no buy, trigger logged out_of_band with the ask seen")
    w65c = World(30, no_bids=((0.35, 40.0),)); w65c.jump(2.5)
    ck(not w65c.recs("paper_buy") and w65c.recs("trigger")[0]["outcome"] == "out_of_band" and w65c.recs("trigger")[0]["ask"] == 0.65,
       "(c) ask 0.65 -> no buy")
    w90 = World(30, no_bids=((0.10, 40.0),)); w90.jump(2.5)
    w70 = World(30, no_bids=((0.30, 40.0),)); w70.jump(2.5)
    ck(len(w90.recs("paper_buy")) == 1 and len(w70.recs("paper_buy")) == 1, "the band edges 0.70 and 0.90 are bought")
    # the book must come from snapshot + deltas: a delta that pulls the 85c level leaves the 90c level, out of band
    wd = World(30, no_bids=((0.15, 40.0), (0.05, 100.0)))
    wd.frame(delta_frame(wd.tk, "no", 0.15, -40.0, seq=2))
    wd.jump(2.5)
    td = wd.recs("trigger")[0] if wd.recs("trigger") else {}
    ck(not wd.recs("paper_buy") and td.get("outcome") == "out_of_band" and td.get("ask") == 0.95 and td.get("ask_size") == 100.0,
       "a delta pulling the 85c level leaves 95c x 100 as the best ask: out of band (the book is snapshot + deltas)")
    wd2 = World(30, no_bids=((0.15, 40.0),))
    wd2.frame(delta_frame(wd2.tk, "no", 0.15, 25.0, seq=2))
    wd2.jump(2.5)
    ck(wd2.recs("paper_buy") and wd2.recs("paper_buy")[0]["qty"] == 65.0, "a delta adding 25 at the 85c level -> 65 bought")
    # (d) a second qualifying jump in the same market -> no second buy
    for s in range(w.s_jump + 1, w.s_jump + 5):
        w.feed(s)
    w.jump(2.5, sec=w.s_jump + 5)
    ck(len(w.recs("paper_buy")) == 1 and w.tr.n_triggers == 2 and w.recs("trigger")[-1]["outcome"] == "already_bought",
       "(d) a second qualifying jump at tau 25 -> no second buy (already_bought)")
    # no book yet -> no buy
    wb = World(30)
    wb.tr.books[wb.tk] = Book()
    wb.jump(2.5)
    ck(not wb.recs("paper_buy") and wb.recs("trigger")[0]["outcome"] == "no_book", "no snapshot yet -> no buy (no_book)")
    # a print arriving 5 s late by the wall clock is not acted on
    wl = World(30)
    wl.jump(2.5, lag=5.0)
    ck(not wl.recs("paper_buy") and wl.recs("trigger")[0]["outcome"] == "stale_print", "a print 5 s old by the wall clock -> no buy (stale_print)")
    # (e) settlement from the 60 prints: YES bought, average above the strike -> qty x (1 - price) - fee
    we = World(30, base=745.30, strike=745.00)
    we.jump(2.5)
    for s in range(we.s_jump + 1, we.C):
        we.feed(s)
    we.T[0] = we.C + SETTLE_WAIT + 1
    we.tr.settle_due(we.T[0])
    st = we.recs("paper_settle")
    exp = 40 * (1 - 0.85) - FEE40
    ck(len(st) == 1 and st[0]["result"] == "yes" and st[0]["src"] == "calc" and st[0]["n_prints"] == 60 and abs(st[0]["pnl"] - exp) < 1e-9,
       "(e) YES bought, 60-print average above the strike -> win, pnl %.4f = 40 x 0.15 - 0.36" % (st[0]["pnl"] if st else 0))
    ck(st and st[0]["result_lifecycle"] is None and st[0]["result_calc"] == "yes" and abs(we.tr.run_pnl - exp) < 1e-9, "(e) booked from the prints (no lifecycle yet), run pnl %.4f" % we.tr.run_pnl)
    # ... and a lifecycle message arriving later confirms it (no second settle)
    we.frame({"type": "market_lifecycle_v2", "sid": 1, "seq": 1, "msg": {"market_ticker": we.tk, "event_type": "determined", "result": "yes", "determination_ts": we.C + 1}})
    ck(len(we.recs("paper_settle")) == 1 and we.recs("lifecycle_late") and we.recs("lifecycle_late")[0]["agree"] is True and not we.recs("settle_corrected"),
       "(e) a late lifecycle 'yes' confirms the booked result, nothing re-booked")
    # YES bought, average below the strike -> -qty x price - fee; settled by the lifecycle message when it arrives
    wf = World(30, base=744.00, strike=745.00)
    wf.jump(2.5)
    for s in range(wf.s_jump + 1, wf.C):
        wf.feed(s)
    wf.T[0] = wf.C + 1.2
    wf.frame({"type": "market_lifecycle_v2", "sid": 1, "seq": 1, "msg": {"market_ticker": wf.tk, "event_type": "determined", "result": "no", "determination_ts": wf.C + 1}})
    st = wf.recs("paper_settle")
    exp = -40 * 0.85 - FEE40
    ck(len(st) == 1 and st[0]["result"] == "no" and st[0]["src"] == "lifecycle" and st[0]["result_calc"] == "no" and st[0]["agree"] is True and abs(st[0]["pnl"] - exp) < 1e-9,
       "(e) YES bought, average below the strike, lifecycle 'no' -> loss, pnl %.4f = -40 x 0.85 - 0.36; calc and lifecycle agree" % (st[0]["pnl"] if st else 0))
    wf.tr.settle_due(wf.C + SETTLE_WAIT + 5)
    ck(len(wf.recs("paper_settle")) == 1 and wf.tr.n_settled == 1 and wf.tr.n_lost == 1, "(e) settle_due does not book it twice")
    # Kalshi disagrees with the computed result: the lifecycle wins and the pnl is corrected
    wg = World(30, base=745.30, strike=745.00)
    wg.jump(2.5)
    for s in range(wg.s_jump + 1, wg.C):
        wg.feed(s)
    wg.tr.settle_due(wg.C + SETTLE_WAIT + 1)
    wg.frame({"type": "market_lifecycle_v2", "sid": 1, "seq": 1, "msg": {"market_ticker": wg.tk, "event_type": "determined", "result": "no"}})
    ck(bool(wg.recs("settle_corrected")) and abs(wg.tr.run_pnl - (-40 * 0.85 - FEE40)) < 1e-9 and wg.tr.n_lost == 1 and wg.tr.n_settled == 1,
       "a later lifecycle result that disagrees corrects the booked pnl to the loss")
    # the strike can arrive from the lifecycle channel
    wm = World(30, strike=None)
    wm.frame({"type": "market_lifecycle_v2", "sid": 1, "seq": 1, "msg": {"market_ticker": wm.tk, "event_type": "metadata_updated", "floor_strike": 745.00,
                                                                           "custom_strike": {"round_digits": "2"}, "strike_type": "greater_or_equal"}})
    ck(wm.tr.markets[wm.tk]["strike"] == 745.0 and wm.tr.markets[wm.tk]["rd"] == 2 and wm.recs("strike")[-1]["src"] == "lifecycle",
       "metadata_updated sets the strike 745.00 with round_digits 2")
    # (f) the sd uses the trailing 300 one-second changes and ignores a gap
    wgap = World(30, gap_at=(1793156400 - 30 - 200, 1793156400 - 30 - 195))     # 5 missing seconds inside the window
    sg = wgap.tr.sig[IID]
    # expected: changes over the last 300 seconds where both seconds exist; the change across the gap does not count
    pr = wgap.tr.prints[IID]
    lo_s = wgap.s_jump - SIGW
    ds = [pr[s] - pr[s - 1] for s in range(lo_s, wgap.s_jump) if s in pr and (s - 1) in pr]
    mu = sum(ds) / len(ds); var = sum((x - mu) ** 2 for x in ds) / (len(ds) - 1)
    ck(sg.n == len(ds) == SIGW - 6 and abs(sg.sd() - math.sqrt(var)) < 1e-9,
       "(f) a 5-s gap: %d valid changes in the 300 slots (300 - 5 missing - 1 across the gap), sd %.6f matches a direct computation" % (sg.n, sg.sd()))
    ck(len(sg.q) == SIGW, "(f) the window is 300 slots by the clock, gap slots included")
    wgap2 = World(30, gap_at=(1793156400 - 30 - 100, 1793156400 - 30 - 95))
    wgap2.jump(5.0)                                   # control: a gap earlier in the window, the jump between consecutive seconds
    ck(wgap2.tr.n_triggers == 1, "(f) a 5-sd move between two consecutive seconds does trigger (control, gap earlier in the window)")
    wgap3 = World(30)
    wgap3.feed(wgap3.s_jump + 3, wgap3.v + wgap3.sd() * 5)    # seconds s_jump..s_jump+2 missing: a reconnect
    ck(wgap3.tr.n_triggers == 0 and wgap3.tr.sig[IID].q[-1] is None and wgap3.tr.sig[IID].n == SIGW - 4,
       "(f) a 5-sd move across a 3-s reconnect gap is not a change: no trigger, nothing added to the sd, 3 empty slots")
    sgm = Sigma()
    for s in range(100, 100 + SIGMIN):
        sgm.push(s, 1.0 + (s % 2) * 0.1)
    ck(sgm.sd() is None and (sgm.push(100 + SIGMIN, 1.0) is not None) and sgm.sd() is not None,
       "(f) the sd is None under 150 valid changes and appears at 150")
    ck(sgm.push(100, 5.0) == "dup" and sgm.n == SIGMIN, "(f) an old or repeated print is ignored")
    wpr = World(30)
    wpr.frame({"type": "cfbenchmarks_value", "sid": 2, "seq": 9, "msg": {"index_id": IID, "data": json.dumps({"time": (wpr.s_jump) * 1000 + 500, "value": "999"})}})
    ck(wpr.tr.sig[IID].last_sec == wpr.s_jump - 1 and wpr.tr.n_triggers == 0, "a print not on the whole second is skipped (scan.py: time % 1000)")
    wpr.frame({"type": "cfbenchmarks_value", "sid": 2, "seq": 10, "msg": {"index_id": IID, "data": "not json"}})
    ck(wpr.recs("bad_print"), "an unreadable print is logged, not fatal")
    # (g) --live raises SystemExit before any order
    wlive = World(30, live=True)
    raised = None
    try:
        wlive.jump(2.5)
    except SystemExit as e:
        raised = str(e)
    ck(raised == "live order path not built" and not wlive.recs("paper_buy") and not wlive.tr.held and not wlive.tr.bought,
       "(g) --live: SystemExit('live order path not built') before any order; nothing booked")
    # (h) the stop file ends the run cleanly
    global STOP_FILE
    real = STOP_FILE
    STOP_FILE = os.path.join(tempfile.gettempdir(), "jumpband-selftest-%d.stop" % os.getpid())
    try:
        ws_ = World(30)
        ck(not ws_.tr.check_stop_file(), "(h) no stop file -> running")
        open(STOP_FILE, "w").close()
        t0 = time.time()
        asyncio.run(watch_stop(ws_.tr, time.time() + 30, ws_.log, period=0.05))
        ck(ws_.tr.stopped and time.time() - t0 < 5 and ws_.recs("stop_file") and ws_.recs("stopping"),
           "(h) the stop file: the watcher returns within a tick and logs stop_file + stopping (the run then ends)")
        ws_.jump(2.5)
        ck(not ws_.recs("paper_buy") and ws_.recs("trigger")[-1]["outcome"] == "stopped", "(h) after the stop a qualifying jump is logged, not bought")
    finally:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
        STOP_FILE = real
    # fast coins: off by default, on with --fast-k 4 at band 70-95c
    wfast = World(30, series="KXBTC15M")
    ck(wfast.tk not in wfast.tr.markets, "fast coins are not watched without --fast-k")
    wfast4 = World(30, series="KXBTC15M", fast_k=4.0, no_bids=((0.07, 40.0),))
    ck(wfast4.iid == "BRTI" and wfast4.tk in wfast4.tr.markets, "--fast-k 4: BTC is watched on the BRTI index")
    wfast4.jump(3.0)
    ck(wfast4.tr.n_triggers == 0, "--fast-k 4: a 3-sd BTC move is not a trigger")
    wfast4.jump(4.0, sec=wfast4.s_jump + 1)
    fb = wfast4.recs("paper_buy")
    ck(wfast4.tr.n_triggers == 1 and len(fb) == 1 and fb[0]["ask"] == 0.93 and fb[0]["k"] == 4.0 and fb[0]["band"] == [0.70, 0.95],
       "--fast-k 4: a 4-sd BTC move with the ask at 0.93 is bought (band 70-95c)")
    # health and market_done records
    we.tr.health(ws_up=False)
    h = we.recs("health")[-1]
    ck(h["paper_buys"] == 1 and h["settled"] == 1 and abs(h["paper_pnl"] - (40 * 0.15 - FEE40)) < 1e-9 and "prints_per_s" in h and h["markets"] == 1,
       "health: markets, books, prints per second, triggers, paper buys, paper pnl")
    md = we.recs("market_done")
    ck(len(md) == 1 and md[0]["bought"] is True and md[0]["triggers"] == 1, "market_done summary once the close has passed")
    we.tr.settle_due(we.C + FORGET_S + 1)
    ck(we.tk not in we.tr.markets and we.tk not in we.tr.books, "a settled market is forgotten 20 min after its close")
    # REST row -> market
    row = {"ticker": "KXBNB15M-26OCT272300-00", "close_time": "2026-10-28T03:00:00Z", "floor_strike": 744.5, "custom_strike": {"round_digits": "2"}}
    tk_, c_, k_, rd_, src_ = market_from_rest(row, "KXBNB15M")
    ck(c_ == 1793156400 and k_ == 744.5 and rd_ == 2 and src_ == "floor_strike", "a /markets row gives close 03:00Z, strike 744.5, round_digits 2")
    ck(fee(1, 0.85) == 0.01 and fee(100, 0.70) == 1.47 and fee(0, 0.8) == 0.0 and fee(100, 0.85) == 0.9 and fee(53, 0.83) == 0.53,
       "fee: 1 contract at 85c rounds up to 1c; 100 at 70c = 1.47; 100 at 85c = 0.90; 53 at 83c = 0.53")
    print("SELFTEST", ("FAILED: %s" % fails) if fails else "PASSED", "(%d checks)" % n[0])
    return not fails


# ---------------------------------------------------------------------------------------------------- main
def main():
    global LOG
    ap = argparse.ArgumentParser(description="jump-band buyer on the 15-minute crypto markets, paper arm")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--live", action="store_true", help="STUB: refuses to run (live order path not built)")
    ap.add_argument("--series", default=",".join(SLOW), help="comma list (default %s)" % ",".join(SLOW))
    ap.add_argument("--k", type=float, default=K)
    ap.add_argument("--lo", type=float, default=LO)
    ap.add_argument("--hi", type=float, default=HI)
    ap.add_argument("--fast-k", type=float, default=None, help="also watch %s at k >= this, band %.2f-%.2f" % ("/".join(s[2:-3] for s in FAST), FAST_LO, FAST_HI))
    ap.add_argument("--max-contracts", type=float, default=MAX_CONTRACTS)
    ap.add_argument("--minutes", type=float, default=20160)
    ap.add_argument("--log", default=LOG)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if a.live:
        raise SystemExit("live order path not built")
    series = [s.strip() for s in a.series.split(",") if s.strip()]
    bad = [s for s in series if s not in INDEX]
    if bad:
        raise SystemExit("unknown series %s; known: %s" % (bad, sorted(INDEX)))
    if a.fast_k is not None:
        if a.fast_k < 4.0:
            raise SystemExit("--fast-k must be at least 4 (the replay backs the fast coins only at k >= 4)")
        series = series + [s for s in FAST if s not in series]
    elif any(s in FAST for s in series):
        raise SystemExit("fast coins (%s) need --fast-k 4" % ", ".join(s for s in series if s in FAST))
    if not (0.5 <= a.lo < a.hi <= 0.99) or a.k < 1.0 or a.max_contracts <= 0:
        raise SystemExit("0.5 <= --lo < --hi <= 0.99, --k >= 1, --max-contracts > 0")
    if not selftest():
        raise SystemExit("selftest failed; refusing to run")
    if os.path.exists(STOP_FILE):
        raise SystemExit("stop file present: %s" % STOP_FILE)
    LOG = a.log
    log = Logger(LOG)
    tr = Trader(log, live=False, k=a.k, lo=a.lo, hi=a.hi, max_contracts=a.max_contracts, fast_k=a.fast_k)
    log.write("start", pid=os.getpid(), live=False, paper=True, series=series, index_ids=sorted({INDEX[s] for s in series}),
              k=a.k, lo=a.lo, hi=a.hi, fast_k=a.fast_k, fast_band=[FAST_LO, FAST_HI], max_contracts=a.max_contracts,
              tau=[TAU_LO, TAU_HI], sigma_window=SIGW, sigma_min=SIGMIN, max_lag_s=MAX_LAG, settle_wait_s=SETTLE_WAIT,
              minutes=a.minutes, log=LOG, stop_file=STOP_FILE, python=sys.version.split()[0], argv=sys.argv)
    print("jumpband PAPER: %s, k %.1f, band %.2f-%.2f, fast-k %s, cap %.0f, %g minutes; log %s" % (
        ",".join(series), a.k, a.lo, a.hi, a.fast_k, a.max_contracts, a.minutes, LOG), flush=True)
    try:
        asyncio.run(run_live(tr, a.minutes, log, series))
    finally:
        log.write("exit", triggers=tr.n_triggers, paper_buys=tr.n_buys, settled=tr.n_settled, lost=tr.n_lost, paper_pnl=tr.run_pnl,
                  open_positions=sum(1 for v in tr.held.values() if not v["settled"]), stopped=tr.stopped)


if __name__ == "__main__":
    main()
