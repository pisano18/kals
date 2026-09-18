#!/usr/bin/env python3
r"""pindesk.py -- the desktop app. START / PAUSE / STOP, and what an owner needs to see.

THE OPERATOR, 2026-09-17: "it should be a proper tool on my desktop with a
dashboard and status viewer and controls. Make it so it's a program on my
desktop and I can click start pause and stop. Make it that simple so anyone can
do it." Then, on the first version: percentage returns next to the money ("I
like to treat this like an investment"), an interactive chart, a help feature
because "I don't know what everything means", a view of how active the market
is ("not too many people were selling or orders weren't filling"), whether each
hedge turned out to be needed, click-to-sort on every table, and the recorders
named with what they actually do.

WHAT THE THREE BUTTONS DO -- and, more important, what they never do.

  START   removes the stand-down flag (results\pinrun-live.stop), makes sure
          the watchdogs are running (boot_all.ps1), and if the bot is not
          alive starts it through restart_bot.ps1 -- THE ONLY script that may
          start the live bot, with all of its rails (refuses while a bet is
          held and the bot is alive, proves the old pid is gone, never starts
          a second live bot).
  PAUSE   writes the stand-down flag so the watchdog stops relaunching, waits
          for every open bet to SETTLE (research\pinflat.py decides), then
          stops the bot. Nothing is abandoned mid-bet. START resumes.
  STOP    writes the flag and stops the bot NOW. If a bet is open it asks
          first: the bet still settles on Kalshi by itself, but it will not
          be hedged.

Stopping is by pid from results\pinrun-live.pid, and ONLY after that process's
command line has been read and contains `pinrun.py` and `--live`. If Windows
returns the command line empty (it does, for a process the caller cannot open
-- the 2026-09-14 double-bot incident) the app REFUSES to kill and says so,
rather than guess. The collectors are never touched by anything here.

EVERY NUMBER ON THE SCREEN comes from results\pinrun-live-*.jsonl, the log the
live bot writes as it trades. Nothing is modelled. Days are EASTERN, and so is
the clock inside a ticker (KXXRP15M-26SEP170000-00 closes at midnight ET, which
is 04:00Z -- the first version read it as UTC and put every close four hours
early, which is why its "yesterday" did not match the operator's). Closes are
counted by close time (rule 4): all coins settling on one quarter hour are one
close, won if it made money and lost if it did not.

Runs under pythonw (no console); anything that would have been a traceback
goes to results\pindesk.err instead.

    python research/pindesk.py --selftest
    pythonw research/pindesk.py            # what the desktop shortcut runs
"""
import calendar
import ctypes
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from downtime import et_offset, hours_up_et_day, lost_by_et_day     # noqa: E402
import pinflat                                                       # noqa: E402
import pinlab                                                        # noqa: E402

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
KALS = r"C:\kals"
PY = r"C:\Python314\python.exe"
STOP_FLAG = os.path.join(RESULTS, "pinrun-live.stop")
HEARTBEAT = os.path.join(RESULTS, "watch_bot.heartbeat")
ERR_FILE = os.path.join(RESULTS, "pindesk.err")
REFRESH_MS = 5000
STALE_MIN = 20
CREATE_NO_WINDOW = 0x08000000

C = {"bg": "#0F1420", "panel": "#171E2E", "panel2": "#1D2536", "panel3": "#242E44", "text": "#E6EAF2",
     "muted": "#8A94A8", "gain": "#31C48D", "loss": "#E4572E", "watch": "#F0B429",
     "blue": "#4C8DFF", "grey": "#5B6478"}

GATE_WORDS = {
    "no_offer": "nobody was selling the winning side",
    "edge_floor": "the price was too close to what it is worth (edge too thin)",
    "price_ceiling": "the only offers were above the 98c cap",
    "both_sides": "the book quoted both sides (not settled enough)",
    "depth_floor": "the offer was too small",
    "book_stale": "the order book feed was stale",
    "confidence": "the model was not sure enough yet",
    "ev_floor": "the expected profit after fees was too small",
    "dump": "a suspiciously cheap offer (dump guard)",
    "jump": "the price had just jumped against us (jump gate)",
}


# ===========================================================================
# time and tickers
# ===========================================================================
def parse_t(s):
    """'2026-09-16T13:59:31Z' -> epoch. None if it is not that shape."""
    try:
        return calendar.timegm(time.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def et_day(epoch):
    """ET calendar day of an epoch, as 'YYYY-MM-DD'."""
    e = epoch + et_offset(epoch)
    return time.strftime("%Y-%m-%d", time.gmtime(e))


def et_day_start(day):
    """Epoch of midnight ET at the start of 'YYYY-MM-DD'."""
    y, m, d = (int(x) for x in day.split("-"))
    noon = calendar.timegm((y, m, d, 12, 0, 0))
    return calendar.timegm((y, m, d, 0, 0, 0)) - et_offset(noon)


def et_str(epoch, fmt="%I:%M %p"):
    e = epoch + et_offset(epoch)
    s = time.strftime(fmt, time.gmtime(e))
    return s.lstrip("0") if fmt.startswith("%I") else s


def et_now_str():
    return et_str(time.time(), "%a %b %d %I:%M:%S %p") + " ET"


def coin(ticker):
    m = re.match(r"^KX([A-Z0-9]+?)15M-", str(ticker or ""))
    return m.group(1) if m else str(ticker or "")[:8]


def close_et(ticker):
    c = pinflat.close_epoch(ticker)
    return et_str(c) if c else "?"


def money(x, sign=True):
    return ("$%+.2f" if sign else "$%.2f") % x


def pct(x, sign=True):
    if x is None:
        return "-"
    return ("%+.2f%%" if sign else "%.2f%%") % (100 * x)


def sort_key(v):
    """Numbers sort as numbers whatever they are dressed in ($, +, c, %, x)."""
    s = str(v).strip()
    m = re.match(r"^[\$+]?\s*(-?[\d,]*\.?\d+)\s*(c|%|x|GB|s|h|min)?$", s)
    if m:
        try:
            return (0, float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return (1, s.lower())


# ===========================================================================
# the ledger: everything the live logs say, kept current incrementally
# ===========================================================================
def _bank_from_why(why):
    m = re.search(r"bank \$([0-9][0-9,]*\.?[0-9]*)", str(why or ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


class Ledger:
    def __init__(self, results=RESULTS):
        self.results = results
        self.files = {}            # path -> bytes consumed
        self.settled = []          # dicts with t, tk, pnl ($), cost, want, result, close, file
        self.orders = []
        self.signals = []
        self.hedges = []
        self.autosize = []
        self.halts = []
        self.starts = []
        self.closes = []           # close_summary records, trimmed
        self.newest = None
        self.newest_rows = []      # every row of the newest file (for open positions)

    def _load_kalshi(self):
        """Settled MONEY, one row per MARKET, from Kalshi's own books.

        `results/kalshi_ledger.json` is written by `research/pinledger.py`,
        which reads `/portfolio/settlements`. Everything here is the
        exchange's: what it paid, what both sides cost, what it charged. A
        market we hedged is ONE row with the net, not two legs that each look
        like a separate trade.

        If the cache is missing or unreadable the app shows no settlements
        rather than falling back to the logs -- a wrong number displayed
        confidently is what this replaced.
        """
        try:
            import pinledger
        except ImportError:
            return False
        try:
            mtime = os.path.getmtime(pinledger.LEDGER)
        except OSError:
            return False
        if mtime == getattr(self, "_kalshi_mtime", None):
            return False
        self._kalshi_mtime = mtime
        # PASS THE PATH. `load_cache(path=LEDGER)` binds its default at import,
        # so pointing `pinledger.LEDGER` somewhere else changes the mtime check
        # here and NOT the file actually read -- the two would silently
        # disagree, which is how the self-test read the real account's books
        # while believing it had been isolated.
        rows = pinledger.load_cache(pinledger.LEDGER)
        out = []
        for s in rows.values():
            tk = s.get("ticker") or ""
            st = s.get("settled_time") or ""
            out.append({
                "t": parse_t(st[:19] + "Z" if len(st) > 19 else st),
                "tk": tk,
                "pnl": pinledger.pnl(s),
                "cost": None,
                "want": s.get("market_result"),
                "result": s.get("market_result"),
                "close": pinflat.close_epoch(tk),
                "file": "kalshi",
                "hedged": (pinledger.money(s, "yes_count_fp") > 0
                           and pinledger.money(s, "no_count_fp") > 0),
                "book": "oil" if tk.split("-")[0] in (
                    "KXGOLD15M", "KXWTI15M", "KXSILVER15M",
                    "KXCOPPER15M", "KXNATGAS15M") else "crypto",
            })
        out.sort(key=lambda s: s["t"] or 0)
        self.settled = out
        return True

    def refresh(self):
        # BOTH LIVE BOTS. Added 2026-09-18: the commodity bot writes to
        # cmdlive-*.jsonl and NOTHING read it, so the desktop app and the
        # Telegram bot both showed a crypto-only total. On 2026-09-17 that
        # reported "+$88 today" on a day that was +$88 crypto and -$58 oil.
        # A number that silently omits one of two live bots is worse than no
        # number. The record shapes differ (the commodity log has `won` where
        # the crypto log has `want`/`cost`), and `_ingest` reads every one of
        # those with .get(), so a missing field shows blank instead of lying.
        paths = sorted(glob.glob(os.path.join(self.results, "pinrun-live-*.jsonl"))
                       + glob.glob(os.path.join(self.results, "cmdlive-*.jsonl")))
        if not paths:
            return False
        changed = False
        newest = max(paths, key=os.path.getmtime)
        if newest != self.newest:
            self.newest = newest
            self.newest_rows = []
            self.files.pop(newest, None)
        for p in paths:
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            done = self.files.get(p, 0)
            if size <= done:
                continue
            with open(p, "rb") as fh:
                fh.seek(done)
                chunk = fh.read()
            cut = chunk.rfind(b"\n")
            if cut < 0:
                continue
            for line in chunk[:cut + 1].splitlines():
                try:
                    r = json.loads(line.decode("utf-8", "replace"))
                except ValueError:
                    continue
                self._ingest(r, p)
                if p == newest:
                    self.newest_rows.append(r)
            self.files[p] = done + cut + 1
            changed = True
        # Money comes from Kalshi, and it replaces self.settled wholesale --
        # the log pass above contributes signals, orders and gates only.
        if self._load_kalshi():
            changed = True
        return changed

    def _ingest(self, r, path):
        k = r.get("kind")
        t = parse_t(r.get("t"))
        f = os.path.basename(path)
        if k == "settled":
            # DELIBERATELY IGNORED. Money now comes from Kalshi's own
            # settlements (`_load_kalshi`), never from our logs. The logs
            # record one line PER LEG, and a hedged market has two -- so this
            # path reported `KXDOGE15M-26SEP180015-15` as a -$3.93 LOSS (the
            # 11c YES hedge leg, alone) on a market that Kalshi settled at
            # +$4.36. It also double-counted days, missed the positions that
            # were open when a process was killed, and had no idea the
            # commodity bot existed. A tool that reports legs cannot report a
            # day. See pinledger.py.
            return
        elif k == "order":
            try:
                filled = float(r.get("filled") or 0)
            except (TypeError, ValueError):
                filled = 0.0
            asked = None
            try:
                asked = float((r.get("body") or {}).get("count"))
            except (TypeError, ValueError, AttributeError):
                pass
            self.orders.append({"t": t, "tk": r.get("ticker"), "filled": filled,
                                "asked": asked, "price": r.get("exec_price"),
                                "status": r.get("status"), "swept": bool(r.get("swept")),
                                "fee": r.get("fee_total"), "latency_ms": r.get("latency_ms"),
                                "ask_seen": r.get("ask_seen"), "limit_sent": r.get("limit_sent"),
                                "tau": r.get("tau_at_send"), "error": r.get("error"),
                                "close": pinflat.close_epoch(r.get("ticker")), "file": f})
        elif k == "signal":
            self.signals.append({"t": t, "tk": r.get("ticker"), "want": r.get("want"),
                                 "price": r.get("price"), "edge_c": r.get("edge_c"),
                                 "size": r.get("size"), "take_n": r.get("take_n"),
                                 "tau": r.get("tau"), "fair": r.get("fair"), "spot": r.get("spot"),
                                 "strike": r.get("strike"), "digits": r.get("digits"),
                                 "level_age_ms": r.get("level_age_ms"), "file": f})
        elif k in ("hedge", "hedge_alarm"):
            self.hedges.append({"t": t, "kind": k, "tk": r.get("ticker"),
                                "belief": r.get("belief"), "n": r.get("n"),
                                "price": r.get("price"), "status": r.get("status"),
                                "side": r.get("side"), "entry": r.get("entry"),
                                "tau": r.get("tau"), "file": f})
        elif k == "autosize":
            self.autosize.append({"t": t, "size": r.get("new"), "bank": _bank_from_why(r.get("why")),
                                  "file": f})
        elif k in ("halt", "end"):
            self.halts.append({"t": t, "kind": k, "why": r.get("why"), "file": f})
        elif k == "start":
            self.starts.append({"t": t, "file": f, "size": r.get("size"),
                                "hedge": r.get("hedge_belief"), "tau_max": r.get("tau_max"),
                                "mode": r.get("mode")})
        elif k == "close_summary":
            looks = r.get("looks") or 0
            dep = r.get("depth") or {}
            self.closes.append({
                "t": t, "close": r.get("close"), "looks": looks,
                "no_offer": r.get("no_offer") or 0, "tradeable": r.get("tradeable") or 0,
                "fired": bool(r.get("fired")), "gates": r.get("gates") or {},
                "best_edge_c": r.get("best_edge_c"), "best_price": r.get("best_price"),
                "best_ticker": r.get("best_ticker"), "best_want": r.get("best_want"),
                "depth_med": dep.get("median") if isinstance(dep, dict) else None,
                "why": r.get("why"), "file": f})

    # ---- aggregations ----
    @staticmethod
    def by_close(settled):
        """{close_epoch: net $} -- one entry per CLOSE (rule 4)."""
        out = {}
        for s in settled:
            key = s["close"] if s["close"] is not None else s["t"]
            out[key] = out.get(key, 0.0) + s["pnl"]
        return out

    @staticmethod
    def summary(settled):
        closes = Ledger.by_close(settled)
        won = sum(1 for v in closes.values() if v >= 0)
        lost = len(closes) - won
        net = sum(closes.values())
        worst = min(closes.values()) if closes else 0.0
        best = max(closes.values()) if closes else 0.0
        wins = [v for v in closes.values() if v >= 0]
        losses = [v for v in closes.values() if v < 0]
        return {"closes": len(closes), "won": won, "lost": lost, "net": net,
                "worst": worst, "best": best, "markets": len(settled),
                "loss_rate": (100.0 * lost / len(closes)) if closes else None,
                "avg_win": (sum(wins) / len(wins)) if wins else None,
                "avg_loss": (sum(losses) / len(losses)) if losses else None}

    def settled_on(self, day):
        return [s for s in self.settled if s["t"] and et_day(s["close"] or s["t"]) == day]

    def fills_on(self, day):
        return [o for o in self.orders if o["t"] and et_day(o["close"] or o["t"]) == day]

    def signals_on(self, day):
        return [s for s in self.signals if s["t"] and et_day(s["t"]) == day]

    def closes_on(self, day):
        return [c for c in self.closes if c["close"] and et_day(c["close"]) == day]

    @staticmethod
    def fill_stats(orders):
        f = [o for o in orders if o["filled"] > 0]
        zero = sum(1 for o in orders if o["filled"] <= 0)
        contracts = sum(o["filled"] for o in f)
        asked = sum(o["asked"] for o in orders if o["asked"])
        pcts = sorted(o["filled"] / o["asked"] for o in f if o["asked"])
        med = pcts[len(pcts) // 2] if pcts else None
        return {"orders": len(orders), "fills": len(f), "zero": zero,
                "contracts": contracts, "asked": asked, "median_pct": med,
                "share": (contracts / asked) if asked else None}

    def days(self):
        seen = {}
        for s in self.settled:
            if s["t"]:
                seen.setdefault(et_day(s["close"] or s["t"]), True)
        for o in self.orders:
            if o["t"]:
                seen.setdefault(et_day(o["close"] or o["t"]), True)
        return sorted(seen)

    def bank(self):
        for a in reversed(self.autosize):
            if a["bank"] is not None:
                return a
        return None

    def first_bank(self):
        for a in self.autosize:
            if a["bank"] is not None and a["t"]:
                return a
        return None

    def deposited(self):
        """What the account started with. If results\\DEPOSITED.txt holds a
        number, that is the operator's own figure and wins. Otherwise: the
        first real bank reading minus the profit made before it (the bot only
        began reading the balance on 2026-09-13), which is a reconstruction."""
        try:
            with open(os.path.join(self.results, "DEPOSITED.txt"), encoding="utf-8") as fh:
                v = float(re.sub(r"[^0-9.]", "", fh.read().split("\n")[0]))
                if v > 0:
                    return v
        except (OSError, ValueError):
            pass
        fb = self.first_bank()
        if not fb:
            return None
        before = sum(s["pnl"] for s in self.settled if s["t"] and s["t"] < fb["t"])
        return fb["bank"] - before

    def bank_at(self, epoch):
        """The bank at an instant: the last real reading at or before it, plus
        every settlement since. Between readings this is a reconstruction."""
        last = None
        for a in self.autosize:
            if a["bank"] is not None and a["t"] and a["t"] <= epoch:
                last = a
        if last is None:
            dep = self.deposited()
            if dep is None:
                return None
            return dep + sum(s["pnl"] for s in self.settled if s["t"] and s["t"] <= epoch)
        return last["bank"] + sum(s["pnl"] for s in self.settled if s["t"] and last["t"] < s["t"] <= epoch)

    def bank_series(self):
        """(t, bank) over time: real readings marked real=True, settlements
        between them reconstructed."""
        pts = []
        for s in self.settled:
            if s["t"]:
                b = self.bank_at(s["t"])
                if b is not None:
                    pts.append((s["t"], b, False))
        for a in self.autosize:
            if a["bank"] is not None and a["t"]:
                pts.append((a["t"], a["bank"], True))
        pts.sort()
        return pts

    def contracts_for(self, ticker):
        return sum(o["filled"] for o in self.orders if o["tk"] == ticker)

    def last_halt(self):
        return self.halts[-1] if self.halts else None

    def last_start(self):
        return self.starts[-1] if self.starts else None

    def run_settled(self):
        f = os.path.basename(self.newest) if self.newest else None
        return [s for s in self.settled if s["file"] == f]

    def losing_closes(self):
        """Every losing close, all time, newest first: (close, net, legs)."""
        rows = {}
        for s in self.settled:
            key = s["close"] if s["close"] is not None else s["t"]
            d = rows.setdefault(key, {"net": 0.0, "legs": []})
            d["net"] += s["pnl"]
            d["legs"].append(s)
        out = [(k, v["net"], v["legs"]) for k, v in rows.items() if v["net"] < 0]
        out.sort(key=lambda x: -(x[0] or 0))
        return out

    def hedge_outcomes(self):
        """Each executed hedge joined to how the bet ended. 'needed' when the
        bet it protected LOST (the hedge paid), 'wasted' when the bet held."""
        out = []
        merged = {}                    # one hedge per ticker: several tries add up
        for g in self.hedges:
            if g["kind"] != "hedge" or str(g.get("status")) != "executed":
                continue
            m = merged.get(g["tk"])
            if m is None:
                merged[g["tk"]] = dict(g)
            else:
                n0, n1 = float(m.get("n") or 0), float(g.get("n") or 0)
                if n0 + n1 > 0 and m.get("price") is not None and g.get("price") is not None:
                    m["price"] = (float(m["price"]) * n0 + float(g["price"]) * n1) / (n0 + n1)
                m["n"] = n0 + n1
        for g in merged.values():
            # THE VERDICT IS NOW READ FROM THE MARKET, NOT THE LEGS. Money
            # comes from Kalshi as ONE row per market, so there is no longer a
            # separate "hedge leg" P&L to look up -- and that is the honest
            # view anyway: what a hedge cost or saved is the difference between
            # the market's net and what the unhedged bet would have paid.
            # `market_result` tells us which way it went; the hedge was NEEDED
            # when the side we originally held is the side that LOST.
            legs = [s for s in self.settled if s["tk"] == g["tk"]]
            side = g.get("side")                 # the side the HEDGE bought
            net = sum(s["pnl"] for s in legs) if legs else None
            res = next((s.get("result") for s in legs if s.get("result")), None)
            verdict = None
            if res:
                # the hedge bought `side`; it was needed if `side` won
                verdict = "NEEDED" if str(res).lower() == str(side).lower() else "WASTED"
            out.append(dict(g, bet_pnl=None, hedge_pnl=None, verdict=verdict,
                            net=net, result=res))
        return out

    # ---- market activity ----
    @staticmethod
    def offer_share(c):
        return (1.0 - c["no_offer"] / c["looks"]) if c["looks"] else None

    def activity(self, last_n=4):
        """How active sellers are right now against the whole record."""
        shares = [Ledger.offer_share(c) for c in self.closes]
        shares = sorted(s for s in shares if s is not None)
        recent = [Ledger.offer_share(c) for c in self.closes[-last_n:]]
        recent = [s for s in recent if s is not None]
        if not shares or not recent:
            return {"level": "UNKNOWN", "recent": None, "p25": None, "p75": None, "median": None}
        rec = sorted(recent)[len(recent) // 2]
        p25 = shares[len(shares) // 4]
        med = shares[len(shares) // 2]
        p75 = shares[(3 * len(shares)) // 4]
        level = "QUIET" if rec < p25 else ("BUSY" if rec > p75 else "NORMAL")
        return {"level": level, "recent": rec, "p25": p25, "median": med, "p75": p75}

    @staticmethod
    def why_no_trade(c):
        if c["fired"]:
            return "BOUGHT"
        if c.get("why") and "NOBODY OFFERED" in str(c["why"]).upper():
            return GATE_WORDS["no_offer"]
        g = {k: v for k, v in (c.get("gates") or {}).items() if k != "no_offer"}
        if not g:
            return GATE_WORDS["no_offer"] if c["no_offer"] else "nothing passed"
        k = max(g, key=g.get)
        return GATE_WORDS.get(k, k)

    def reason(self, c):
        """What happened on a quarter-hour, in words -- checking OUR ORDERS
        first. 'tradeable' in the bot's summary only means somebody was
        selling at SOME price; the offer usually then failed a rule. And an
        order that was sent and got nothing is a lost race, not a rule."""
        if c["fired"]:
            got = sum(o["filled"] for o in self.orders if o["close"] == c["close"])
            return "BOUGHT %g contracts" % got
        sent = [o for o in self.orders if o["close"] == c["close"]]
        if sent:
            asked = sum(o["asked"] or 0 for o in sent)
            return "LOST THE RACE: ordered %g, got 0 (someone bought it first)" % asked
        return Ledger.why_no_trade(c)


# ===========================================================================
# stories -- one bet, one hedge, one quarter-hour, one day, in plain words
# ===========================================================================
def _fmt_px(v, digits):
    try:
        return ("%%.%df" % int(digits or 2)) % float(v)
    except (TypeError, ValueError):
        return str(v)


def _find_signal(ledger, tk, before=None):
    for s in reversed(ledger.signals):
        if s["tk"] == tk and (before is None or (s["t"] or 0) <= before + 1):
            return s
    return None


def _saw(sig, side):
    """'WHAT IT SAW' for a signal, for the side it wanted."""
    if not sig:
        return "WHAT IT SAW: (no signal record found for this bet)"
    fair = sig.get("fair")
    chance = None
    if fair is not None:
        chance = float(fair) if side == "YES" else 1.0 - float(fair)
    worth = (100 * chance) if chance is not None else None
    spot = _fmt_px(sig.get("spot"), sig.get("digits"))
    strike = _fmt_px(sig.get("strike"), sig.get("digits"))
    rel = "above" if side == "YES" else "below"
    out = ("WHAT IT SAW: with %s seconds left the price stood at %s and the line was %s. "
           "The bet is that it finishes %s the line." % (sig.get("tau", "?"), spot, strike, rel))
    if worth is not None:
        out += (" The model put the chance of that at %.2f%%, so a %s contract was worth about %.1fc. "
                "Someone was selling it at %.1fc -- %.2fc cheaper than that (the \"edge\")."
                % (worth, side, worth, 100 * float(sig.get("price") or 0), float(sig.get("edge_c") or 0)))
    age = sig.get("level_age_ms")
    if age is not None:
        try:
            out += " That offer had been sitting there %.1f s." % (float(age) / 1000.0)
        except (TypeError, ValueError):
            pass
    return out


def _did(orders):
    if not orders:
        return "WHAT IT DID: sent no order."
    parts = []
    for o in orders:
        if o["filled"] > 0:
            p = "bought %g contracts at %.1fc" % (o["filled"], 100 * float(o["price"] or 0))
            if o.get("asked") and o["filled"] < o["asked"] - 1e-9:
                p += " (asked for %g; the seller had fewer)" % o["asked"]
            if o.get("fee") is not None:
                p += ", fee $%.2f" % float(o["fee"])
            if o.get("latency_ms") is not None:
                p += ", the order took %.0f ms" % float(o["latency_ms"])
            if o.get("swept") and o.get("ask_seen") is not None and o.get("limit_sent") is not None:
                p += " (it saw %.1fc and was willing to pay up to %.1fc so a faster buyer could not beat it)" % (
                    100 * float(o["ask_seen"]), 100 * float(o["limit_sent"]))
        else:
            p = "asked for %g contracts and got NONE -- someone else bought that offer first (a lost race)" % float(o.get("asked") or 0)
            if o.get("error"):
                p += "; error: %s" % str(o["error"])[:80]
        parts.append(p)
    return "WHAT IT DID: " + "; ".join(parts) + "."


def story_settled(ledger, s):
    tk = s["tk"]
    side = str(s["want"]).upper()
    close = s["close"]
    hedges = [g for g in ledger.hedge_outcomes() if g["tk"] == tk]
    is_hedge_leg = any(str(g.get("side")).upper() == side for g in hedges)
    head = "%s -- the market closing %s ET on %s" % (coin(tk), close_et(tk), et_str(close, "%b %d") if close else "?")
    lines = [head, ""]
    if is_hedge_leg:
        g = next(g for g in hedges if str(g.get("side")).upper() == side)
        lines.append("THIS ROW IS THE INSURANCE LEG of a hedge: %g %s contracts bought at %.0fc when the model's belief in the "
                     "original bet fell to %.0f%%." % (float(g.get("n") or 0), side, 100 * float(g.get("price") or 0), 100 * float(g.get("belief") or 0)))
        lines.append("")
        lines.append("HOW IT WENT: the market settled %s, so this leg %s: %s." % (
            str(s["result"]).upper(), "paid $1.00 a contract" if s["pnl"] >= 0 else "paid nothing", money(s["pnl"])))
        lines.append("Double-click the original bet's row (same coin, same close, the other side) for the whole story.")
        return "\n".join(lines)
    sig = _find_signal(ledger, tk, s["t"])
    orders = [o for o in ledger.orders if o["tk"] == tk]
    n = sum(o["filled"] for o in orders)
    lines.append(_saw(sig, side))
    lines.append("")
    lines.append(_did(orders))
    lines.append("")
    res = str(s["result"]).upper()
    if s["pnl"] >= 0:
        lines.append("HOW IT WENT: the market settled %s -- the side it held. Each contract paid $1.00. After the price paid "
                     "and the fee, the bet made %s (%.2fc per contract)." % (res, money(s["pnl"]), 100 * s["pnl"] / n if n else 0))
    else:
        lines.append("HOW IT WENT: the market settled %s -- AGAINST the side it held. The contracts paid nothing, so the money "
                     "paid for them is lost: %s. The price must have crossed the line inside the final seconds, which the model "
                     "put at under 1 in 200 -- and every such loss costs many wins." % (res, money(s["pnl"])))
    for g in hedges:
        if g["verdict"] is None:
            continue
        lines.append("")
        lines.append("INSURANCE: at belief %.0f%% it bought %g %s at %.0fc. That turned out %s: the hedge leg made %s, so the close "
                     "finished at %s instead of %s." % (100 * float(g.get("belief") or 0), float(g.get("n") or 0),
                                                       str(g.get("side")).upper(), 100 * float(g.get("price") or 0),
                                                       g["verdict"], money(g["hedge_pnl"] or 0), money(g["net"] or 0), money(g["bet_pnl"] or 0)))
    return "\n".join(lines)


def story_hedge(ledger, g):
    tk = g["tk"]
    side = str(g.get("side")).upper()
    other = "NO" if side == "YES" else "YES"
    n_bet = sum(o["filled"] for o in ledger.orders if o["tk"] == tk)
    lines = ["%s -- insurance on the market closing %s ET on %s" % (coin(tk), close_et(tk), et_str(g["t"], "%b %d") if g["t"] else "?"), ""]
    lines.append("WHAT HAPPENED: with %s seconds left the bot held %g %s contracts bought at %.1fc. The price moved toward the "
                 "line and the model's belief that the bet would win fell to %.0f%% (it acts under 60%%). So it bought %g contracts "
                 "of the other side, %s, at %.0fc." % (g.get("tau", "?"), n_bet, other, 100 * float(g.get("entry") or 0),
                                                        100 * float(g.get("belief") or 0), float(g.get("n") or 0), side, 100 * float(g.get("price") or 0)))
    lines.append("")
    lines.append("WHY: if the bet then loses, the %s contracts pay $1.00 each and cover part of the loss. If the bet wins anyway, "
                 "the insurance is lost -- a small cost for a big saving when it is needed. It recovers about a third of a loss on average." % side)
    lines.append("")
    # The market's NET is all we can honestly quote now: Kalshi settles a
    # hedged market as one row, so there is no separate "what the bet alone
    # did" to compare against. Splitting it was how the old tool reported a
    # hedge leg as its own losing trade.
    net = g.get("net")
    if g["verdict"] == "NEEDED":
        lines.append("HOW IT WENT: NEEDED. The side the bot originally held did lose, and the insurance covered part of it. "
                     "The market finished at %s, which is better than the unhedged bet would have paid."
                     % (money(net) if net is not None else "not settled yet"))
    elif g["verdict"] == "WASTED":
        lines.append("HOW IT WENT: WASTED, this time. The original bet held, so the insurance expired worthless. "
                     "The market still finished at %s. That is the premium for being covered when it does flip."
                     % (money(net) if net is not None else "not settled yet"))
    else:
        lines.append("HOW IT WENT: not settled yet.")
    return "\n".join(lines)


def story_signal(ledger, s):
    side = str(s["want"]).upper()
    tk = s["tk"]
    orders = [o for o in ledger.orders if o["tk"] == tk and o["t"] and s["t"] and 0 <= o["t"] - s["t"] <= 10]
    lines = ["%s -- a buy decision at %s ET for the market closing %s" % (coin(tk), et_str(s["t"], "%I:%M:%S %p") if s["t"] else "?", close_et(tk)), ""]
    lines.append(_saw(s, side))
    lines.append("")
    lines.append(_did(orders))
    settled = [x for x in ledger.settled if x["tk"] == tk and x["want"] == s["want"]]
    if settled and any(o["filled"] > 0 for o in orders):
        lines.append("")
        lines.append("HOW IT WENT: %s, %s. Double-click the bet in LAST SETTLED BETS for the full story." % (
            "WON" if settled[0]["pnl"] >= 0 else "LOST", money(settled[0]["pnl"])))
    return "\n".join(lines)


def story_loss(ledger, close, net, legs):
    lines = ["The quarter-hour closing %s ET on %s lost %s" % (et_str(close), et_str(close, "%b %d"), money(net)), ""]
    for l in legs:
        n = ledger.contracts_for(l["tk"])
        lines.append("  %s %s at %.1fc, %g contracts -> settled %s: %s" % (
            coin(l["tk"]), str(l["want"]).upper(), 100 * float(l["cost"] or 0), n, str(l["result"]).upper(), money(l["pnl"])))
    lines.append("")
    lines.append("WHY IT HURTS: a win here makes 2c to 4c a contract; a loss costs most of the 96c-98c paid. So one losing close "
                 "wipes out many winning ones, and the list on this tab is what decides a day.")
    lines.append("Double-click a row in LAST SETTLED BETS for what the bot saw and did on each leg.")
    return "\n".join(lines)


def story_close(ledger, c):
    share = Ledger.offer_share(c)
    passed = (c["tradeable"] / c["looks"]) if c["looks"] else None
    lines = ["The quarter-hour closing %s ET on %s" % (et_str(c["close"]), et_str(c["close"], "%b %d")) if c["close"] else "A quarter-hour", ""]
    lines.append("The bot checked the books %d times in the last 30 seconds." % c["looks"])
    if share is not None:
        lines.append("On %.0f%% of those checks somebody was selling the winning side at some price." % (100 * share))
    _ = passed
    if c.get("best_edge_c") is not None:
        lines.append("The best bargain seen was %.2fc of edge at %.1fc%s." % (
            c["best_edge_c"], 100 * float(c.get("best_price") or 0), (" on " + coin(c["best_ticker"])) if c.get("best_ticker") else ""))
    if c.get("depth_med") is not None:
        lines.append("A typical offer held %.0f contracts." % c["depth_med"])
    g = c.get("gates") or {}
    if g:
        words = ["%s (%d)" % (GATE_WORDS.get(k, k), v) for k, v in sorted(g.items(), key=lambda kv: -kv[1])]
        lines.append("Why looks were passed over: " + "; ".join(words) + ".")
    lines.append("")
    if c["fired"]:
        lines.append("RESULT: " + ledger.reason(c).lower() + " on this quarter-hour.")
    else:
        lines.append("RESULT: no trade -- " + ledger.reason(c) + ".")
    return "\n".join(lines)


def story_day(ledger, d, now=None):
    now = time.time() if now is None else now
    s = Ledger.summary(ledger.settled_on(d))
    fs = Ledger.fill_stats(ledger.fills_on(d))
    b0 = ledger.bank_at(et_day_start(d))
    cl = ledger.closes_on(d)
    wo = sum(1 for c in cl if c["no_offer"] < c["looks"])
    try:
        up = hours_up_et_day(d, now if d == et_day(now) else et_day_start(d) + 86400)
    except Exception:                                    # noqa: BLE001
        up = None
    lines = ["%s (Eastern day)" % d, ""]
    lines.append("MONEY: %s, which is %s of the $%.2f the bank held when the day started." % (money(s["net"]), pct((s["net"] / b0) if b0 else None), b0 or 0))
    lines.append("BETS: %d closes (%d contracts bought over %d fills), %d won, %d lost. %s" % (
        s["closes"], fs["contracts"], fs["fills"], s["won"], s["lost"],
        ("The worst close cost %s." % money(s["worst"])) if s["lost"] else "No losing close."))
    lines.append("SELLERS: of %d quarter-hours watched, %d had somebody selling. %d orders were sent; %d filled; %d were lost races."
                 % (len(cl), wo, fs["orders"], fs["fills"], fs["zero"]))
    if fs["share"] is not None:
        lines.append("FILL: it asked for %g contracts and got %g (%s). This share is what limits growth as bets get bigger." % (
            fs["asked"], fs["contracts"], pct(fs["share"], False)))
    if up:
        lines.append("TIME: the bot could trade %.1f hours of this day: %s per hour." % (up, money(s["net"] / up)))
    return "\n".join(lines)


# ===========================================================================
# health
# ===========================================================================
def _file_age_s(path):
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return None


def _ram_free_gb():
    try:
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / 1e9
    except Exception:                                   # noqa: BLE001
        return None


def recorder_ok(root):
    """Same proof of life restart_bot.ps1 uses: the previous UTC hour landed
    with bytes, and a file is open for the hour in progress."""
    now = time.time()
    prev = time.strftime("%Y%m%dT%H", time.gmtime(now - 3600)) + ".jsonl.gz"
    cur = time.strftime("%Y%m%dT%H", time.gmtime(now)) + ".jsonl.gz"
    pb = 0
    cn = 0
    chans = []
    try:
        for name in os.listdir(root):
            d = os.path.join(root, name)
            if not os.path.isdir(d):
                continue
            p = os.path.join(d, prev)
            c = os.path.join(d, cur)
            if os.path.exists(p):
                try:
                    pb += os.path.getsize(p)
                except OSError:
                    pass
            if os.path.exists(c):
                cn += 1
                chans.append(name)
    except OSError:
        pass
    return pb > 0 and cn > 0, pb, cn, chans


def newest_mtime_age(root):
    best = None
    try:
        for dp, _dn, fn in os.walk(root):
            for f in fn:
                try:
                    m = os.path.getmtime(os.path.join(dp, f))
                except OSError:
                    continue
                if best is None or m > best:
                    best = m
    except OSError:
        pass
    return None if best is None else time.time() - best


def read_flag():
    try:
        with open(STOP_FLAG, encoding="utf-8") as fh:
            return fh.read().strip() or "(no reason)"
    except OSError:
        return None


def last_line(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        return lines[-1].strip() if lines else ""
    except OSError:
        return ""


def health(ledger):
    h = {}
    pid = pinflat.live_pid()
    h["pid"] = pid
    h["alive"] = bool(pid) and pinflat.pid_alive(pid)
    h["flag"] = read_flag()
    ages = [a for a in (_file_age_s(ledger.newest) if ledger.newest else None,
                        _file_age_s(os.path.join(RESULTS, "pinrun-live.out"))) if a is not None]
    h["quiet_s"] = min(ages) if ages else None
    h["watchdog_s"] = _file_age_s(HEARTBEAT)
    h["phone_s"] = _file_age_s(os.path.join(RESULTS, "pinphone.heartbeat"))
    try:
        with open(os.path.join(KALS, "logs", "run_all.pid")) as fh:
            h["run_all"] = pinflat.pid_alive(int(fh.read().strip()))
    except (OSError, ValueError):
        h["run_all"] = None
    h["kalshi_ok"], h["kalshi_prev"], h["kalshi_open"], h["kalshi_chans"] = recorder_ok(os.path.join(KALS, "kalshi_data"))
    h["feeds_ok"], h["feeds_prev"], h["feeds_open"], h["feeds_chans"] = recorder_ok(os.path.join(KALS, "feed_data"))
    h["cdc_age"] = newest_mtime_age(os.path.join(KALS, "cdc_data"))
    now = time.time()
    h["paper_arms"] = sum(1 for p in glob.glob(os.path.join(RESULTS, "pinrun-paper-*.jsonl"))
                          if now - os.path.getmtime(p) < 900)
    h["race_arms"] = sum(1 for p in glob.glob(os.path.join(RESULTS, "pinracearm-*.jsonl"))
                         if now - os.path.getmtime(p) < 900)
    try:
        h["disk_gb"] = shutil.disk_usage("C:\\").free / 1e9
    except OSError:
        h["disk_gb"] = None
    h["ram_gb"] = _ram_free_gb()
    try:
        st, d = pinflat.check()
        h["flat"] = st
        h["open"] = d.get("open") or {}
    except Exception as e:                              # noqa: BLE001
        h["flat"] = "UNKNOWN"
        h["open"] = {}
        h["flat_err"] = str(e)[:120]
    h["halt"] = ledger.last_halt()
    h["boot_last"] = last_line(os.path.join(RESULTS, "boot_all.log"))
    h["watch_last"] = last_line(os.path.join(RESULTS, "watch_bot.log"))
    return h


def evidence(h):
    """What the state was DERIVED from, so the banner is never a label
    somebody set. THE OPERATOR: 'make sure ... it's actually derived by
    checking if it's running or not and not trusting'. The process is checked
    by opening its pid; 'trading' means its own log was written recently; the
    stand-down flag is a file on disk, read every refresh."""
    q = h.get("quiet_s")
    return "Checked just now: process %s %s; its log was written %s; stand-down flag %s." % (
        h.get("pid") or "?", "is OPEN (alive)" if h["alive"] else "is NOT running",
        ("%d s ago" % q) if q is not None else "never",
        "PRESENT" if h.get("flag") else "absent")


def status_of(h, now=None):
    """(state, headline, detail, colour) for the banner. Every state is
    derived from evidence(h), never from a stored label."""
    st = _status_of(h, now)
    return (st[0], st[1], st[2] + "\n" + evidence(h), st[3])


def _status_of(h, now=None):
    now = time.time() if now is None else now
    n_open = sum(v if isinstance(v, (int, float)) else (v.get("n", 1) if isinstance(v, dict) else 1)
                 for v in (h.get("open") or {}).values())
    if h["alive"]:
        if h.get("flag"):
            if n_open:
                return ("PAUSING", "PAUSING -- finishing %d open bet%s first" % (n_open, "" if n_open == 1 else "s"),
                        "No new bets. It stops by itself when they settle.", C["watch"])
            return ("PAUSING", "STOPPING -- stand-down flag is set", "The bot will be stopped in a moment.", C["watch"])
        q = h.get("quiet_s")
        if q is not None and q > STALE_MIN * 60:
            return ("STALE", "RUNNING BUT QUIET for %d min" % int(q / 60),
                    "Nothing written to its log. The watchdog restarts it after %d min of silence." % 25, C["watch"])
        return ("TRADING", "TRADING  (pid %s)" % h["pid"],
                "%d open bet%s" % (n_open, "" if n_open == 1 else "s") if n_open else "No open bets right now.", C["gain"])
    if h.get("flag"):
        why = h["flag"]
        word = "PAUSED" if "PAUSE" in why.upper() else "STOPPED"
        return (word, "%s by you" % word, "Press START to trade again. (%s)" % why, C["grey"])
    halt = h.get("halt")
    if halt and halt.get("kind") == "halt" and halt.get("why") and \
            re.search(r"loss COUNT brake|loss abort|DRAWDOWN brake", halt["why"]):
        age = (now - halt["t"]) / 60 if halt.get("t") else None
        left = max(0, 15 - age) if age is not None else None
        return ("BRAKE", "STOPPED BY A SAFETY BRAKE",
                "%s%s" % (halt["why"][:110], (" -- watchdog restarts in ~%d min, or press START now." % left) if left is not None else ""),
                C["loss"])
    wd = h.get("watchdog_s")
    if wd is None or wd > 120:
        return ("DOWN", "NOT RUNNING -- and the watchdog is not running either",
                "Press START. It starts the watchdog and the bot.", C["loss"])
    return ("DOWN", "NOT RUNNING -- watchdog is bringing it back",
            "Last watchdog check %d s ago. If this lasts more than a few minutes, press START." % int(wd), C["loss"])


# ===========================================================================
# controls
# ===========================================================================
def _ps(script, *args, timeout=180):
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       creationflags=CREATE_NO_WINDOW, cwd=REPO)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _cmdline(pid):
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % int(pid)],
                       capture_output=True, text=True, timeout=30, creationflags=CREATE_NO_WINDOW)
    return (r.stdout or "").strip()


def terminate_live_bot(log):
    """Stop the live bot by pid, only after proving what that pid is."""
    pid = pinflat.live_pid()
    if not pid or not pinflat.pid_alive(pid):
        log("bot is not running; nothing to stop")
        return True
    cl = _cmdline(pid)
    if "pinrun.py" not in cl or "--live" not in cl:
        log("REFUSING to stop pid %s: its command line reads %r -- cannot prove it is the live bot. "
            "Stop it from a terminal: Stop-Process -Id %s -Force" % (pid, cl[:80], pid))
        return False
    r = subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True,
                       creationflags=CREATE_NO_WINDOW)
    time.sleep(2)
    if pinflat.pid_alive(pid):
        log("taskkill did not stop pid %s: %s" % (pid, (r.stdout + r.stderr).strip()[:120]))
        return False
    log("stopped live bot pid %s" % pid)
    return True


def write_flag(reason):
    with open(STOP_FLAG, "w", encoding="utf-8") as fh:
        fh.write("%s at %s" % (reason, et_now_str()))


def clear_flag():
    try:
        os.remove(STOP_FLAG)
    except OSError:
        pass


def do_start(log):
    clear_flag()
    log("stand-down flag cleared")
    code, out = _ps(os.path.join(REPO, "boot_all.ps1"), "-NoArms")
    for l in out.strip().splitlines()[-3:]:
        log("boot_all: " + l.strip())
    pid = pinflat.live_pid()
    if pid and pinflat.pid_alive(pid):
        log("bot already running, pid %s -- watchdog re-armed" % pid)
        return
    log("starting the bot through restart_bot.ps1 ...")
    code, out = _ps(os.path.join(REPO, "restart_bot.ps1"))
    for l in out.strip().splitlines():
        l = l.strip()
        if l and not l.startswith("*") and "transcript" not in l.lower():
            log("restart_bot: " + l)
    log("restart_bot exit code %d" % code)


def do_pause(log, set_status):
    write_flag("operator PAUSE")
    log("stand-down flag written; watchdog will not relaunch")
    while True:
        st, d = pinflat.check()
        if not d.get("alive"):
            log("bot is not running; paused")
            return
        if st == "FLAT":
            break
        opn = d.get("open") or {}
        soon = []
        for tk in opn:
            c = pinflat.close_epoch(tk)
            soon.append("%s closes %s" % (coin(tk), close_et(tk)) if c else coin(tk))
        set_status("PAUSING -- waiting for %d open bet(s): %s" % (len(opn), ", ".join(soon)[:80]))
        time.sleep(5)
    terminate_live_bot(log)


def do_stop(log):
    write_flag("operator STOP")
    log("stand-down flag written; watchdog will not relaunch")
    terminate_live_bot(log)


# ===========================================================================
# help text -- plain words, one entry per panel and per column
# ===========================================================================
HELP = [
    ("what", "WHAT THE BOT DOES", """\
Kalshi runs a market every 15 minutes on each coin: "will the price be above X at the close?"
The close price is an AVERAGE of the last 60 seconds. With 30 seconds left, half of that
average is already locked in, so the bot can be very sure which side wins. It buys that side
when someone is selling it a little too cheap -- typically 96c to 98c for a contract that pays
$1.00 -- and holds to the close.

A win makes 2c to 4c per contract (minus a fee of about a tenth of a cent). A loss costs most
of the 96c-98c paid. So one loss wipes out many wins, and LOSSES ARE THE WHOLE STORY: a good
day is a day with few losses, not a day with many wins.

The bot sizes each bet from the bank (bank divided by about 5.9), never more than 2 bets on one
quarter-hour, and buys insurance (a "hedge") when a bet it holds starts to look wrong."""),
    ("banner", "THE BIG BANNER AND THE THREE BUTTONS", """\
TRADING (green)   the bot is running and writing its log.
PAUSED / STOPPED (grey)   you pressed PAUSE or STOP. Nothing restarts it until you press START.
NOT RUNNING (red)   it is down and the watchdog is bringing it back (or the watchdog is down too).
SAFETY BRAKE (red)   the bot stopped itself: two losing bets in one run, or the run lost more than
                    its limit, or the bank fell 20% from its high. The watchdog relaunches it
                    15 minutes later. Press START to relaunch sooner.
RUNNING BUT QUIET (yellow)   alive, but nothing logged for 20+ minutes. Watchdog restarts at 25.

START   clears your stand-down, makes sure the watchdogs are up, starts the bot if it is down.
PAUSE   no new bets; waits for any open bet to settle; then stops. Safe at any moment.
STOP    stops right now. Asks first if a bet is open (the bet still settles on Kalshi by
        itself, but there will be nobody to hedge it)."""),
    ("chips", "THE STRIP UNDER THE BUTTONS", """\
BOT        alive or not, and how many seconds since it last wrote to its log.
WATCHDOG   the helper that relaunches the bot when it dies. It checks every 30 seconds.
RECORDERS  the two programs taping the market for research (see the System tab). They are
           worth more than the bot: their tape cannot be re-made if it is lost.
DISK FREE  the tape stops for good below 5 GB. Yellow under 10, red under 6.
RAM FREE   red under 1.5 GB.
BANK       the account balance the bot last read, and the return on what was put in.
SIZE PER BET   how many contracts the bot asks for per bet right now (grows with the bank)."""),
    ("tiles", "TODAY / YESTERDAY / THIS RUN / ALL TIME", """\
The dollar figure is money actually settled, after fees. Under it:
  % return      that money as a share of the bank at the START of that day (all time: of what
                was put in). This is the number to compare with any other investment.
  closes        a close is one quarter-hour. Every coin settling on that quarter-hour counts as
                ONE close, because they all move together. "bets" is the individual contracts
                bought. A close is LOST if it lost money overall.
  hours up      how much of the day the bot was able to trade, and $ per hour of that.
  fills / contracts   how many orders filled, and how many contracts in total.
THIS RUN is since the bot last (re)started."""),
    ("open", "OPEN BETS", """\
Bets bought and not yet settled. "Closes at" is when the market settles (ET); "In" is seconds
to go. A bet settles within about a minute of its close."""),
    ("settled", "LAST SETTLED BETS", """\
Coin      which market.        Close   the quarter-hour it settled on (ET).
Side      YES = bet the price finishes above the line, NO = below.
Paid      cents per contract. At 98c a win makes 2c a contract; a loss costs 98c.
Contracts how many were bought.   $   what the bet made or lost after fees.
Click any column heading to sort by it. Click again to flip the order."""),
    ("signals", "LAST SIGNALS", """\
Every time the bot decided to buy. Edge c = how many cents cheaper the offer was than what the
model says the contract is worth (bigger is better, but the biggest edges are also where
informed sellers hide). Wanted = contracts asked for. Got = contracts actually received --
0 means someone else bought that offer first (we lose about a quarter of these races); a partial
number means the seller had fewer than we wanted."""),
    ("hedges", "HEDGES", """\
When a bet the bot holds starts to look wrong (its "belief" that the bet wins drops under 60%),
it buys the OTHER side as insurance so the worst case is smaller.
  Bet flipped?   NEEDED = the bet did lose, the insurance paid.  WASTED = the bet won anyway and
                 the insurance cost a little.  Pending = not settled yet.
  Bet $ / Hedge $ / Net   what the original bet made, what the insurance made, and the total.
Over time insurance costs a little on quiet days and saves a lot on bad ones."""),
    ("market", "MARKET -- HOW ACTIVE SELLERS ARE", """\
The bot can only buy when someone is SELLING the winning side cheaply in the last 30 seconds.
This tab shows how often that happened.
  QUIET / NORMAL / BUSY   how the last four quarter-hours compare with the whole record.
  looks          how many times the bot checked the books in that quarter-hour.
  sellers seen   share of those looks where anybody was selling the winning side at ANY price.
                 Most such offers then fail a rule: too close to what the contract is worth
                 (an offer at 99.9c), or above the 98c cap.
  best edge      the best bargain seen, in cents.  offer size   contracts on offer (median).
  what happened  BOUGHT, LOST THE RACE (we ordered, someone else got it first), or the main
                 reason the offers were turned down.
Below the table: today's counts -- closes with anything to buy, orders sent, filled, and
lost races (someone else took the offer first)."""),
    ("days", "DAYS", """\
One row per Eastern day. % return is net $ over the bank at the start of that day. Hours up is
the time the bot was able to trade (outages are recorded in results/DOWNTIME.json). Median fill %
is what share of the contracts it asked for the book actually handed over -- THE number that
decides how far the bank can grow, because bets grow with the bank but the sellers do not.
Fill share is the same thing over all contracts. Closes w/ offers = quarter-hours where anybody
was selling at all."""),
    ("chart", "THE CHART", """\
Hover to read a point. Modes:
  Money made    every settled bet added up over time.
  Bank          the account balance: real readings are dots, the line between them is the
                readings plus settlements since (a reconstruction).
  Per day $ / %   one bar per Eastern day.
Range buttons narrow the time window."""),
    ("losses", "LOSSES", """\
Every losing close, all time. This is the list that decides whether the strategy works: it wins
small and loses big, so a few rows here explain most of any bad day."""),
    ("system", "SYSTEM", """\
Every program that has to be running, what it does, and proof it is alive.
LIVE BOT             the one that spends money (research/pinrun.py --live).
BOT WATCHDOG         relaunches the bot when it dies (watch_bot.ps1).
BOOT TASK            Windows task "KalsBoot": at sign-in and every 10 minutes, starts anything
                     that is missing (boot_all.ps1).
KALSHI RECORDER      tapes Kalshi's own feed: prices, trades, full order books, and the
                     settlement index (one print per second). One file per channel per hour.
                     This tape is how every rule was found; it cannot be re-made.
EXCHANGE RECORDER    tapes the order books of Coinbase, Kraken, Bitstamp and Gemini, the
                     exchanges whose prices make up the settlement index.
CRYPTO.COM RECORDER  tapes Crypto.com's prediction markets every few seconds, in case that
                     becomes a second venue.
PAPER ARMS           copies of the bot with one setting changed each, pretending to trade,
                     so a change can be judged before it touches money."""),
    ("log", "LOG", """\
Top: what this app did (start/pause/stop and their results).
Bottom: the bot's own console and the watchdog's log, newest at the end."""),
]


# ===========================================================================
# GUI
# ===========================================================================
def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    ledger = Ledger()
    ledger.refresh()

    root = tk.Tk()
    root.title("Pin Bot")
    root.configure(bg=C["bg"])
    root.geometry("1240x800")
    root.minsize(960, 640)

    def _tk_err(*a):
        with open(ERR_FILE, "a", encoding="utf-8") as fh:
            fh.write("%s tk callback:\n%s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), "".join(traceback.format_exception(*a))))
    root.report_callback_exception = _tk_err

    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=C["bg"], foreground=C["text"], fieldbackground=C["panel"])
    st.configure("TFrame", background=C["bg"])
    st.configure("TNotebook", background=C["bg"], borderwidth=0)
    st.configure("TNotebook.Tab", background=C["panel"], foreground=C["muted"], padding=(14, 6), font=("Segoe UI", 10, "bold"))
    st.map("TNotebook.Tab", background=[("selected", C["panel2"])], foreground=[("selected", C["text"])])
    st.configure("Treeview", background=C["panel"], fieldbackground=C["panel"], foreground=C["text"],
                 rowheight=24, font=("Consolas", 10), borderwidth=0)
    st.configure("Treeview.Heading", background=C["panel2"], foreground=C["muted"], font=("Segoe UI", 9, "bold"))
    st.map("Treeview", background=[("selected", C["blue"])])
    st.configure("Vertical.TScrollbar", background=C["panel2"], troughcolor=C["bg"], arrowcolor=C["muted"])

    # ---- tooltip ----
    class Tip:
        def __init__(self, w, text):
            self.w, self.text, self.top = w, text, None
            w.bind("<Enter>", self.show)
            w.bind("<Leave>", self.hide)

        def show(self, _e=None):
            if self.top:
                return
            x = self.w.winfo_rootx() + 10
            y = self.w.winfo_rooty() + self.w.winfo_height() + 4
            self.top = tk.Toplevel(self.w)
            self.top.overrideredirect(True)
            self.top.configure(bg=C["panel3"])
            tk.Label(self.top, text=self.text, bg=C["panel3"], fg=C["text"], font=("Segoe UI", 9),
                     justify="left", wraplength=360, padx=8, pady=6).pack()
            self.top.geometry("+%d+%d" % (x, y))

        def hide(self, _e=None):
            if self.top:
                self.top.destroy()
                self.top = None

    # ---- banner ----
    banner = tk.Frame(root, bg=C["grey"], height=110)
    banner.pack(fill="x", padx=12, pady=(12, 6))
    banner.pack_propagate(False)
    head = tk.Label(banner, text="...", bg=C["grey"], fg="white", font=("Segoe UI", 22, "bold"), anchor="w")
    head.pack(fill="x", padx=16, pady=(10, 0))
    sub = tk.Label(banner, text="", bg=C["grey"], fg="white", font=("Segoe UI", 11), anchor="w", justify="left")
    sub.pack(fill="x", padx=16)

    btns = tk.Frame(root, bg=C["bg"])
    btns.pack(fill="x", padx=12, pady=(0, 6))

    def big_button(txt, colour, cmd):
        b = tk.Button(btns, text=txt, command=cmd, bg=colour, fg="white", activebackground=colour,
                      activeforeground="white", font=("Segoe UI", 14, "bold"), width=11, height=1,
                      relief="flat", cursor="hand2", bd=0)
        b.pack(side="left", padx=(0, 10))
        return b

    busy = {"on": False}

    def guarded(fn):
        def run():
            if busy["on"]:
                return
            busy["on"] = True
            for b in (b_start, b_pause, b_stop):
                b.configure(state="disabled")

            def worker():
                try:
                    fn()
                except Exception as e:                  # noqa: BLE001
                    console_log("ERROR: %s" % e)
                    with open(ERR_FILE, "a", encoding="utf-8") as fh:
                        fh.write(traceback.format_exc())
                finally:
                    busy["on"] = False
                    root.after(0, lambda: [b.configure(state="normal") for b in (b_start, b_pause, b_stop)])
                    root.after(500, tick)
            threading.Thread(target=worker, daemon=True).start()
        return run

    def on_start():
        do_start(console_log)

    def on_pause():
        do_pause(console_log, lambda s: root.after(0, lambda: sub.configure(text=s)))

    def on_stop():
        h = health(ledger)
        if h["alive"] and h.get("open"):
            n = len(h["open"])
            ok = messagebox.askyesno("Stop now?",
                                     "The bot is holding %d open bet%s. They still settle on Kalshi by "
                                     "themselves, but the bot will not be there to hedge them.\n\n"
                                     "PAUSE waits for them to settle first. Stop anyway?" % (n, "" if n == 1 else "s"))
            if not ok:
                console_log("stop cancelled")
                return
        do_stop(console_log)

    b_start = big_button("▶  START", C["gain"], guarded(on_start))
    b_pause = big_button("⏸  PAUSE", C["watch"], guarded(on_pause))
    b_stop = big_button("■  STOP", C["loss"], guarded(on_stop))
    Tip(b_start, "Clears your stand-down, makes sure the watchdogs are running, starts the bot if it is down.")
    Tip(b_pause, "No new bets. Waits for open bets to settle, then stops. Press START to resume.")
    Tip(b_stop, "Stops right now. Asks first if a bet is open.")

    def small_button(parent, txt, cmd, **kw):
        b = tk.Button(parent, text=txt, command=cmd, bg=C["panel2"], fg=C["text"], font=("Segoe UI", 10),
                      relief="flat", cursor="hand2", bd=0, padx=10, **kw)
        return b

    small_button(btns, "Open Deck (web view)", lambda: os.startfile(os.path.join(REPO, "open_deck.cmd"))).pack(side="left", padx=(20, 6))
    small_button(btns, "Refresh", lambda: tick(force=True)).pack(side="left")
    b_what = tk.Button(btns, text="?  What's this", command=lambda: start_explain(), bg=C["blue"], fg="white",
                       font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", bd=0, padx=10)
    b_what.pack(side="left", padx=(6, 0))
    Tip(b_what, "Click, then hover over anything on the screen and click it to get it explained. Double-click any row in any table for that item's story.")
    clock = tk.Label(btns, text="", bg=C["bg"], fg=C["muted"], font=("Segoe UI", 10))
    clock.pack(side="right")

    # ---- health strip ----
    strip = tk.Frame(root, bg=C["bg"])
    strip.pack(fill="x", padx=12, pady=(0, 6))
    chips = {}
    chip_tips = {"bot": "Is the money bot running, and when did it last write to its log.",
                 "wd": "The helper that relaunches the bot when it dies. Checks every 30 s.",
                 "rec": "The two market recorders (System tab). Their tape cannot be re-made.",
                 "disk": "The tape stops for good below 5 GB free.",
                 "ram": "Free memory. Red under 1.5 GB.",
                 "bank": "The balance the bot last read, and the return on what was put in.",
                 "size": "Contracts the bot asks for per bet. Grows with the bank."}

    def chip(key, title):
        f = tk.Frame(strip, bg=C["panel"], padx=10, pady=6)
        f.pack(side="left", padx=(0, 6), fill="x", expand=True)
        tk.Label(f, text=title, bg=C["panel"], fg=C["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        v = tk.Label(f, text="...", bg=C["panel"], fg=C["text"], font=("Segoe UI", 11, "bold"))
        v.pack(anchor="w")
        s = tk.Label(f, text="", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 8))
        s.pack(anchor="w")
        chips[key] = (v, s)
        Tip(f, chip_tips[key])

    for key, title in (("bot", "BOT"), ("wd", "WATCHDOG"), ("rec", "RECORDERS"), ("disk", "DISK FREE"),
                       ("ram", "RAM FREE"), ("bank", "BANK"), ("size", "SIZE PER BET")):
        chip(key, title)

    # ---- tabs ----
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ---- "What's this?": a registry of explainable things, a popup, and an
    # overlay mode that highlights whatever the mouse is over and explains it
    # on click. THE OPERATOR: "a question mark somewhere and you click it then
    # you can go hover over what you want to know and click to get your info."
    registry = []                                   # (widget, key, title, text-or-None)
    help_by_key = {k: (t, b) for k, t, b in HELP}

    def register(widget, key, title=None, text=None):
        registry.append((widget, key, title or help_by_key.get(key, (key, ""))[0], text))

    def popup(title, text, key=None, near=None, width=640):
        top = tk.Toplevel(root)
        top.title(title)
        top.configure(bg=C["panel"])
        top.transient(root)
        x = (near[0] if near else root.winfo_rootx() + 120)
        y = (near[1] if near else root.winfo_rooty() + 120)
        top.geometry("+%d+%d" % (min(x, root.winfo_screenwidth() - width - 20), min(y, root.winfo_screenheight() - 360)))
        tk.Label(top, text=title, bg=C["panel"], fg=C["blue"], font=("Segoe UI", 12, "bold"), anchor="w",
                 padx=14, pady=8).pack(fill="x")
        body = tk.Text(top, bg=C["panel2"], fg=C["text"], font=("Segoe UI", 10), relief="flat", wrap="word",
                       padx=12, pady=10, width=int(width / 8), height=min(22, max(6, text.count("\n") + 4)))
        body.insert("end", text)
        body.configure(state="disabled")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        bar = tk.Frame(top, bg=C["panel"])
        bar.pack(fill="x", padx=10, pady=(0, 10))
        if key:
            small_button(bar, "Open the full help", lambda: (top.destroy(), show_help(key))).pack(side="left")
        small_button(bar, "Close", top.destroy).pack(side="right")
        top.bind("<Escape>", lambda _e: top.destroy())
        top.focus_set()

    def explain(entry, near=None):
        w, key, title, text = entry
        body = text or help_by_key.get(key, ("", "No help written for this yet."))[1]
        popup(title, body, key=key, near=near)

    def hit_test(xr, yr):
        best = None
        for entry in registry:
            w = entry[0]
            try:
                if not w.winfo_ismapped():
                    continue
                x0, y0 = w.winfo_rootx(), w.winfo_rooty()
                x1, y1 = x0 + w.winfo_width(), y0 + w.winfo_height()
            except tk.TclError:
                continue
            if x0 <= xr < x1 and y0 <= yr < y1:
                area = (x1 - x0) * (y1 - y0)
                if best is None or area < best[0]:
                    best = (area, entry, (x0, y0, x1, y1))
        return best

    explain_state = {"top": None}

    def end_explain():
        if explain_state["top"]:
            explain_state["top"].destroy()
            explain_state["top"] = None
        root.configure(cursor="")

    def start_explain():
        if explain_state["top"]:
            end_explain()
            return
        top = tk.Toplevel(root)
        top.overrideredirect(True)
        top.attributes("-alpha", 0.35)
        top.attributes("-topmost", True)
        top.geometry("%dx%d+%d+%d" % (root.winfo_width(), root.winfo_height(), root.winfo_rootx(), root.winfo_rooty()))
        cv = tk.Canvas(top, bg="black", highlightthickness=0, cursor="question_arrow")
        cv.pack(fill="both", expand=True)
        cv.create_text(root.winfo_width() // 2, 24, text="WHAT'S THIS?  hover over anything, click it for an explanation.  Esc or right-click to leave.",
                       fill="white", font=("Segoe UI", 13, "bold"))
        explain_state["top"] = top

        def on_move(e):
            cv.delete("hl")
            hit = hit_test(e.x_root, e.y_root)
            if not hit:
                return
            _a, entry, (x0, y0, x1, y1) = hit
            ox, oy = root.winfo_rootx(), root.winfo_rooty()
            cv.create_rectangle(x0 - ox, y0 - oy, x1 - ox, y1 - oy, outline=C["watch"], width=3, tags="hl")
            cv.create_rectangle(x0 - ox, y0 - oy - 22, x0 - ox + 8 * len(entry[2]) + 16, y0 - oy, fill=C["watch"], outline="", tags="hl")
            cv.create_text(x0 - ox + 8, y0 - oy - 11, text=entry[2], fill="black", anchor="w", font=("Segoe UI", 10, "bold"), tags="hl")

        def on_click(e):
            hit = hit_test(e.x_root, e.y_root)
            end_explain()
            if hit:
                explain(hit[1], near=(e.x_root + 10, e.y_root + 10))

        cv.bind("<Motion>", on_move)
        cv.bind("<Button-1>", on_click)
        cv.bind("<Button-3>", lambda _e: end_explain())
        top.bind("<Escape>", lambda _e: end_explain())
        top.focus_set()

    def section(parent, title, key, text=None):
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text=title, bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9, "bold")).pack(side="left")
        q = tk.Label(f, text=" ? ", bg=C["panel2"], fg=C["blue"], font=("Segoe UI", 8, "bold"), cursor="hand2")
        q.pack(side="left", padx=6)
        q.bind("<Button-1>", lambda e, k=key, ttl=title, tx=text: explain((None, k, ttl, tx), near=(e.x_root, e.y_root)))
        f.pack(fill="x", pady=(6, 2), anchor="w")
        return f

    def table(parent, cols, widths, height=8, title=None, key=None, story=None):
        f = tk.Frame(parent, bg=C["bg"])
        if title:
            section(f, title, key or "what")
        inner = tk.Frame(f, bg=C["bg"])
        inner.pack(fill="both", expand=True)
        tv = ttk.Treeview(inner, columns=cols, show="headings", height=height)
        sb = ttk.Scrollbar(inner, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        for c_, w in zip(cols, widths):
            tv.heading(c_, text=c_, command=lambda c=c_, t=tv: sort_tv(t, c))
            tv.column(c_, width=w, anchor="w", stretch=(w > 120))
        for tag, col in (("gain", C["gain"]), ("loss", C["loss"]), ("watch", C["watch"]), ("muted", C["muted"]),
                         ("text", C["text"])):
            tv.tag_configure(tag, foreground=col)
        tv._sort = None
        tv._objs = {}
        tv._story = story
        if story:
            def on_dbl(e, t=tv):
                item = t.identify_row(e.y)
                obj = t._objs.get(item)
                if obj is None:
                    return
                try:
                    txt = t._story(obj)
                except Exception as ex:                  # noqa: BLE001
                    txt = "could not build this story: %s" % ex
                popup(txt.split("\n", 1)[0], txt, key=key, near=(e.x_root + 10, e.y_root + 10))
            tv.bind("<Double-1>", on_dbl)
        register(tv, key or "what", (title or key or "table") + ("  (double-click a row for its story)" if story else ""))
        return f, tv

    def sort_tv(tv, col):
        rows = [(tv.set(i, col), i) for i in tv.get_children("")]
        rev = tv._sort == (col, False)
        rows.sort(key=lambda r: sort_key(r[0]), reverse=rev)
        for n, (_v, i) in enumerate(rows):
            tv.move(i, "", n)
        tv._sort = (col, rev)
        for c in tv["columns"]:
            tv.heading(c, text=c + (" ▼" if (c == col and rev) else (" ▲" if c == col else "")))

    def fill(tv, rows):
        tv.delete(*tv.get_children())
        tv._objs = {}
        for row in rows:
            vals, tag = row[0], row[1]
            item = tv.insert("", "end", values=vals, tags=(tag,) if tag else ())
            if len(row) > 2:
                tv._objs[item] = row[2]
        if tv._sort:
            col, rev = tv._sort
            tv._sort = (col, not rev)
            sort_tv(tv, col)

    for key, (v_, _s) in chips.items():
        register(v_.master, "chips", v_.master.winfo_children()[0].cget("text"), chip_tips[key] + "\n\n" + help_by_key["chips"][1])
    register(banner, "banner", "The status banner")
    register(b_start, "banner", "START", "Clears your stand-down, makes sure the watchdogs are running, and starts the bot if it is down.\n\n" + help_by_key["banner"][1])
    register(b_pause, "banner", "PAUSE", "No new bets. Waits for any open bet to settle, then stops the bot. Press START to resume.\n\n" + help_by_key["banner"][1])
    register(b_stop, "banner", "STOP", "Stops the bot right now. Asks first if a bet is open.\n\n" + help_by_key["banner"][1])

    # NOW tab
    now_tab = ttk.Frame(nb)
    nb.add(now_tab, text="  Now  ")
    tiles = tk.Frame(now_tab, bg=C["bg"])
    tiles.pack(fill="x", pady=(8, 2))
    tile_vals = {}

    def tile(key, title):
        f = tk.Frame(tiles, bg=C["panel"], padx=12, pady=8)
        f.pack(side="left", padx=(0, 6), fill="x", expand=True)
        top = tk.Frame(f, bg=C["panel"])
        top.pack(fill="x")
        tk.Label(top, text=title, bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9, "bold")).pack(side="left")
        q = tk.Label(top, text=" ? ", bg=C["panel2"], fg=C["blue"], font=("Segoe UI", 8, "bold"), cursor="hand2")
        q.pack(side="left", padx=6)
        q.bind("<Button-1>", lambda _e: show_help("tiles"))
        row = tk.Frame(f, bg=C["panel"])
        row.pack(fill="x")
        v = tk.Label(row, text="...", bg=C["panel"], fg=C["text"], font=("Segoe UI", 18, "bold"))
        v.pack(side="left")
        p = tk.Label(row, text="", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 12, "bold"))
        p.pack(side="left", padx=(10, 0), pady=(6, 0))
        s = tk.Label(f, text="", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9), justify="left", anchor="w")
        s.pack(anchor="w")
        tile_vals[key] = (v, p, s)
        register(f, "tiles", title)

    for key, title in (("today", "TODAY (ET)"), ("yday", "YESTERDAY"), ("run", "THIS RUN"), ("all", "ALL TIME")):
        tile(key, title)

    lower = tk.Frame(now_tab, bg=C["bg"])
    lower.pack(fill="both", expand=True)
    left = tk.Frame(lower, bg=C["bg"])
    left.pack(side="left", fill="both", expand=True, padx=(0, 6))
    right = tk.Frame(lower, bg=C["bg"])
    right.pack(side="left", fill="both", expand=True)

    f_open, tv_open = table(left, ("Open bet", "Side", "Contracts", "Paid", "Closes at (ET)", "In"),
                            (110, 60, 80, 70, 110, 60), height=3, title="OPEN BETS", key="open",
                            story=lambda s: story_signal(ledger, s))
    f_open.pack(fill="x")
    f_tr, tv_tr = table(left, ("Settled (ET)", "Coin", "Close", "Side", "Paid", "Contracts", "Result", "$"),
                        (120, 60, 80, 50, 60, 80, 60, 80), height=14, title="LAST SETTLED BETS", key="settled",
                        story=lambda s: story_settled(ledger, s))
    f_tr.pack(fill="both", expand=True)
    f_sig, tv_sig = table(right, ("Seen (ET)", "Coin", "Close", "Side", "Price", "Edge c", "Wanted", "Got"),
                          (120, 60, 80, 50, 60, 60, 70, 70), height=9, title="LAST SIGNALS (what it tried to buy)", key="signals",
                          story=lambda s: story_signal(ledger, s))
    f_sig.pack(fill="both", expand=True)
    f_hg, tv_hg = table(right, ("When (ET)", "Coin", "Belief", "Contracts", "Price", "Bet flipped?", "Bet $", "Hedge $", "Net $"),
                        (120, 55, 60, 70, 55, 100, 70, 70, 70), height=5, title="HEDGES (insurance bought when a bet turned)", key="hedges",
                        story=lambda g: story_hedge(ledger, g))
    f_hg.pack(fill="x")

    # MARKET tab
    mk_tab = ttk.Frame(nb)
    nb.add(mk_tab, text="  Market  ")
    mk_head = tk.Frame(mk_tab, bg=C["panel"], padx=14, pady=10)
    mk_head.pack(fill="x", pady=(8, 4))
    mk_level = tk.Label(mk_head, text="...", bg=C["panel"], fg=C["text"], font=("Segoe UI", 20, "bold"))
    mk_level.pack(side="left")
    mk_desc = tk.Label(mk_head, text="", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 10), justify="left")
    mk_desc.pack(side="left", padx=16)
    f_mk, tv_mk = table(mk_tab, ("Close (ET)", "Looks", "Sellers seen", "Best edge c", "Best price", "Offer size", "What happened"),
                        (110, 70, 100, 90, 80, 90, 420), height=16, title="THE LAST QUARTER-HOURS, NEWEST FIRST", key="market",
                        story=lambda c: story_close(ledger, c))
    f_mk.pack(fill="both", expand=True)
    register(mk_head, "market", "How active sellers are")
    mk_today = tk.Label(mk_tab, text="", bg=C["bg"], fg=C["text"], font=("Segoe UI", 10), justify="left", anchor="w")
    mk_today.pack(fill="x", pady=(4, 6))

    # DAYS tab
    days_tab = ttk.Frame(nb)
    nb.add(days_tab, text="  Days  ")
    f_days, tv_days = table(days_tab, ("Day (ET)", "Net $", "% return", "Closes", "Won", "Lost", "$ / close", "Worst $",
                                       "Hours up", "$ / hour", "Orders", "Filled", "Lost races", "Contracts", "Median fill %", "Fill share", "Closes w/ offers"),
                            (95, 75, 75, 60, 50, 50, 75, 75, 70, 70, 60, 60, 80, 80, 95, 80, 110), height=9,
                            title="EACH DAY, NEWEST FIRST (click a heading to sort)", key="days",
                            story=lambda d: story_day(ledger, d))
    f_days.pack(fill="x", padx=2, pady=(8, 4))
    ch_bar = section(days_tab, "THE CHART", "chart")
    mode_var = tk.StringVar(value="cum")
    range_var = tk.StringVar(value="all")
    for txt, val in (("Money made", "cum"), ("Bank", "bank"), ("Per day $", "day"), ("Per day %", "daypct")):
        tk.Radiobutton(ch_bar, text=txt, variable=mode_var, value=val, command=lambda: draw_chart(),
                       bg=C["bg"], fg=C["text"], selectcolor=C["panel2"], activebackground=C["bg"],
                       activeforeground=C["text"], font=("Segoe UI", 9)).pack(side="left", padx=(8, 0))
    tk.Label(ch_bar, text="   range:", bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
    for txt, val in (("all", "all"), ("month", "30"), ("7 days", "7"), ("3 days", "3"), ("today", "1")):
        tk.Radiobutton(ch_bar, text=txt, variable=range_var, value=val, command=lambda: draw_chart(),
                       bg=C["bg"], fg=C["text"], selectcolor=C["panel2"], activebackground=C["bg"],
                       activeforeground=C["text"], font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))
    # THE READOUT. It used to be a 9pt tooltip chasing the mouse in the corner
    # of the canvas, which is the hardest place on the screen to read. Now it is
    # a fixed line under the controls: the headline number when the mouse is
    # away, and whatever the mouse is over when it is on the chart.
    ch_read = tk.Frame(days_tab, bg=C["panel"], padx=14, pady=8)
    ch_read.pack(fill="x", padx=2, pady=(0, 2))
    ch_big = tk.Label(ch_read, text="", bg=C["panel"], fg=C["text"],
                      font=("Segoe UI", 22, "bold"), anchor="w")
    ch_big.pack(side="left")
    ch_sub = tk.Label(ch_read, text="", bg=C["panel"], fg=C["muted"],
                      font=("Segoe UI", 11), anchor="w", justify="left")
    ch_sub.pack(side="left", padx=(16, 0))
    chart = tk.Canvas(days_tab, bg=C["panel"], highlightthickness=0, height=240)
    chart.pack(fill="both", expand=True, padx=2, pady=(0, 6))
    chart_pts = {"pts": [], "kind": "line"}
    register(chart, "chart", "The chart")

    # LOSSES tab
    loss_tab = ttk.Frame(nb)
    nb.add(loss_tab, text="  Losses  ")
    f_loss, tv_loss = table(loss_tab, ("Close (ET)", "Day", "Net $", "Coins", "Legs", "Paid (avg)", "Contracts"),
                            (140, 100, 90, 200, 60, 90, 90), height=24,
                            title="EVERY LOSING CLOSE, ALL TIME, NEWEST FIRST", key="losses",
                            story=lambda x: story_loss(ledger, *x))
    f_loss.pack(fill="both", expand=True, padx=2, pady=(8, 0))
    loss_sum = tk.Label(loss_tab, text="", bg=C["bg"], fg=C["text"], font=("Segoe UI", 10), justify="left", anchor="w")
    loss_sum.pack(fill="x", pady=(4, 6))

    # SYSTEM tab
    sys_tab = ttk.Frame(nb)
    nb.add(sys_tab, text="  System  ")
    f_sys, tv_sys = table(sys_tab, ("Program", "What it does", "Status", "Proof"),
                          (170, 470, 130, 330), height=10, title="EVERYTHING THAT HAS TO BE RUNNING", key="system")
    f_sys.pack(fill="both", expand=True, padx=2, pady=(8, 4))
    sys_foot = tk.Label(sys_tab, text="", bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9), justify="left", anchor="w")
    sys_foot.pack(fill="x", pady=(0, 6))

    # LAB tab -- the drawing board. Content lives in research/pinlab.py.
    lab_tab = ttk.Frame(nb)
    nb.add(lab_tab, text="  Lab  ")
    lab_head = tk.Frame(lab_tab, bg=C["panel"], padx=14, pady=10)
    lab_head.pack(fill="x", pady=(8, 4))
    lab_count = tk.Label(lab_head, text="", bg=C["panel"], fg=C["text"],
                         font=("Segoe UI", 16, "bold"))
    lab_count.pack(side="left")
    lab_note = tk.Label(lab_head, bg=C["panel"], fg=C["muted"], font=("Segoe UI", 10),
                        justify="left", anchor="w",
                        text="Everything we are trying, everything we shipped, and everything "
                             "that died. The dead ones are kept on purpose --\nhalf of what we "
                             "know came from ideas that looked good and were not.")
    lab_note.pack(side="left", padx=16)
    register(lab_head, "lab", "The drawing board")
    lab_filter = tk.Frame(lab_tab, bg=C["bg"])
    lab_filter.pack(fill="x", padx=2)
    lab_which = tk.StringVar(value="ALL")
    lab_body = tk.Text(lab_tab, bg=C["panel"], fg=C["text"], font=("Segoe UI", 10),
                       relief="flat", wrap="word", padx=14, pady=10)
    # PACKED LATER, below the overlay chart -- tk stacks in pack() order, and
    # an expanding body packed first pushes the chart off the bottom.
    for _w, _v in (("All", "ALL"), ("Running", pinlab.RUNNING), ("Shipped", pinlab.SHIPPED),
                   ("Killed", pinlab.KILLED), ("Ideas", pinlab.IDEA)):
        tk.Radiobutton(lab_filter, text=_w, variable=lab_which, value=_v,
                       command=lambda: draw_lab(), bg=C["bg"], fg=C["text"],
                       selectcolor=C["panel2"], activebackground=C["bg"],
                       activeforeground=C["text"], font=("Segoe UI", 9)).pack(side="left", padx=(8, 0))

    lab_cache = {"prog": {}, "whatif": {}, "names": {}, "b0": {}}

    def lab_whatif(logname):
        """Cached. Computed on the worker thread by lab_compute()."""
        return (lab_cache.get("whatif") or {}).get(logname)

    # ---- the what-if overlay -------------------------------------------
    # The operator, 2026-09-18: *"I don't see anywhere showing what effect it
    # would've had on the actual running bank. I wanted to see how our profit
    # and bankroll would be different if it had been running like it was
    # running... price chart with effect of paper run overlayed the real
    # chart."* The text summary above answers it in percentages; this answers
    # it in dollars, on the same axis as the real balance.
    #
    # BOTH lines start from the SAME real bank reading at the moment the arm
    # started, and both add up realised settlements from there. That is the
    # only way the comparison is fair: a bank curve drawn from real readings
    # for one line and from arithmetic for the other would differ by every
    # deposit and every open position, and would read as strategy.
    lab_pickbar = tk.Frame(lab_tab, bg=C["bg"])
    lab_pickbar.pack(fill="x", padx=2, pady=(6, 0))
    tk.Label(lab_pickbar, text="WHAT IF THIS HAD BEEN LIVE:", bg=C["bg"], fg=C["muted"],
             font=("Segoe UI", 8, "bold")).pack(side="left", padx=(8, 8))
    lab_pick = tk.StringVar(value="")
    lab_pickmenu = tk.OptionMenu(lab_pickbar, lab_pick, "")
    lab_pickmenu.configure(bg=C["panel"], fg=C["text"], font=("Segoe UI", 9),
                           relief="flat", highlightthickness=0,
                           activebackground=C["panel2"], activeforeground=C["text"])
    lab_pickmenu["menu"].configure(bg=C["panel"], fg=C["text"], font=("Segoe UI", 9))
    lab_pickmenu.pack(side="left")
    lab_pickhead = tk.Label(lab_pickbar, text="", bg=C["bg"], fg=C["muted"],
                            font=("Segoe UI", 10, "bold"))
    lab_pickhead.pack(side="left", padx=12)
    lab_chart = tk.Canvas(lab_tab, bg=C["panel"], height=200, highlightthickness=0)
    lab_chart.pack(fill="x", padx=2, pady=(4, 0))

    def lab_menu_refresh():
        """Repopulate the arm picker from whatever the worker just computed."""
        wf = lab_cache.get("whatif") or {}
        names = lab_cache.get("names") or {}
        opts = sorted(names.get(k, k) for k in wf if wf.get(k))
        menu = lab_pickmenu["menu"]
        menu.delete(0, "end")
        for o in opts:
            menu.add_command(label=o, command=lambda v=o: (lab_pick.set(v), draw_lab_chart()))
        if lab_pick.get() not in opts:
            lab_pick.set(opts[0] if opts else "")

    def draw_lab_chart(*_a):
        """Draw only. Every number here came off the worker thread."""
        lab_chart.delete("all")
        wf = lab_cache.get("whatif") or {}
        names = lab_cache.get("names") or {}
        want = lab_pick.get()
        log = None
        for k, v in names.items():
            if v == want and wf.get(k):
                log = k
                break
        w = wf.get(log) if log else None
        if not w or len(w.get("live") or []) < 2 or len(w.get("arm") or []) < 2:
            lab_pickhead.configure(text="")
            lab_chart.create_text(16, 18, anchor="w", fill=C["muted"], font=("Segoe UI", 9),
                                  text="no settled markets on both sides yet, so there is "
                                       "nothing honest to compare")
            return
        b0 = (lab_cache.get("b0") or {}).get(log)
        base = b0 if b0 else 0.0
        lab_pickhead.configure(
            text="%s   %s" % (
                ("%+.1f%% on the money" % w["pct"]) if w.get("pct") is not None
                else money(w["diff"]),
                ("%+.0f%% swing" % w["sd_pct"]) if w.get("sd_pct") is not None
                else "swing not comparable"),
            fg=C["gain"] if w["diff"] > 0 else C["loss"])
        lv = [(t, base + v) for t, v in w["live"]]
        av = [(t, base + v) for t, v in w["arm"]]
        W = max(lab_chart.winfo_width(), 300)
        H = max(int(lab_chart["height"]), 120)
        m = {"l": 60, "r": 132, "t": 14, "b": 22}
        allv = [v for _, v in lv] + [v for _, v in av]
        lo, hi = min(allv), max(allv)
        if hi - lo < 1e-9:
            hi = lo + 1
        pad = (hi - lo) * 0.08
        lo, hi = lo - pad, hi + pad
        ts = [t for t, _ in lv] + [t for t, _ in av]
        t0, t1 = min(ts), max(ts)

        def X(t):
            return m["l"] + (t - t0) / max(1, t1 - t0) * (W - m["l"] - m["r"])

        def Y(v):
            return m["t"] + (hi - v) / (hi - lo) * (H - m["t"] - m["b"])

        if lo <= base <= hi:
            lab_chart.create_line(m["l"], Y(base), W - m["r"], Y(base),
                                  fill=C["grey"], dash=(3, 3))
            lab_chart.create_text(m["l"] - 6, Y(base), text="$%.0f" % base,
                                  fill=C["muted"], anchor="e", font=("Segoe UI", 8))
        for v in (lo, hi):
            lab_chart.create_text(m["l"] - 6, Y(v), text="$%.0f" % v, fill=C["muted"],
                                  anchor="e", font=("Segoe UI", 8))
        last = None
        for t, _v in lv:
            d = et_day(t)
            if d != last:
                lab_chart.create_line(X(t), m["t"], X(t), H - m["b"], fill=C["panel2"])
                lab_chart.create_text(X(t) + 2, H - m["b"] + 9, text=d[5:], fill=C["muted"],
                                      anchor="w", font=("Segoe UI", 8))
                last = d
        for pts, col, wid in ((lv, C["blue"], 2),
                              (av, C["gain"] if w["diff"] > 0 else C["loss"], 2)):
            co = []
            for t, v in pts:
                co += [X(t), Y(v)]
            lab_chart.create_line(*co, fill=col, width=wid)
        for pts, col, txt in (
                (lv, C["blue"], "REAL  $%.0f" % lv[-1][1]),
                (av, C["gain"] if w["diff"] > 0 else C["loss"],
                 "WHAT IF  $%.0f" % av[-1][1])):
            lab_chart.create_text(W - m["r"] + 8, Y(pts[-1][1]), text=txt, fill=col,
                                  anchor="w", font=("Segoe UI", 9, "bold"))
        lab_chart.create_text(W - m["r"] + 8, H - m["b"] + 9, anchor="w", fill=C["muted"],
                              font=("Segoe UI", 8),
                              text="both start at the real balance")

    lab_chart.bind("<Configure>", draw_lab_chart)
    lab_body.pack(fill="both", expand=True, padx=2, pady=(4, 6))


    def lab_compute():
        """Everything the Lab tab needs, computed OFF the interface thread.

        Called from the background worker. Reading a dozen paper logs and
        shelling out to PowerShell takes seconds, and doing that where the app
        draws is what made it freeze on every click.
        """
        cmds = []
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                 "ForEach-Object { $_.CommandLine }"],
                capture_output=True, text=True, timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            cmds = [l for l in (out.stdout or "").splitlines() if l.strip()]
        except Exception:                                         # noqa: BLE001
            cmds = []
        try:
            prog = pinlab.live_progress(cmdlines=cmds)
        except Exception:                                         # noqa: BLE001
            prog = {}
        wf, names, b0s = {}, {}, {}
        bymatch = {e.get("match"): e.get("name") for e in pinlab.EXPERIMENTS}
        live_pts = sorted((s["t"], s["pnl"]) for s in ledger.settled if s.get("t"))
        for match, info in prog.items():
            log = info.get("log")
            if not log or log in wf:
                continue
            try:
                arm_pts, arm_ct = pinlab.arm_series(os.path.join(ledger.results, log))
                if not arm_pts:
                    continue
                t0 = arm_pts[0][0]
                live_ct = sum(float(o.get("filled") or 0) for o in ledger.orders
                              if (o.get("t") or 0) >= t0)
                wf[log] = pinlab.whatif(arm_pts, arm_ct, live_pts, live_ct)
                names[log] = bymatch.get(match) or match
                b0s[log] = ledger.bank_at(t0)
            except Exception:                                     # noqa: BLE001
                continue
        lab_cache["prog"], lab_cache["whatif"] = prog, wf
        lab_cache["names"], lab_cache["b0"] = names, b0s

    def draw_lab():
        lab_body.configure(state="normal")
        lab_body.delete("1.0", "end")
        # NO I/O HERE. This runs on the interface thread, and the first version
        # called PowerShell with an 8 second timeout and then read every paper
        # arm's log -- so the whole app froze on every click and on every
        # refresh. The worker thread fills lab_cache; this only draws it.
        prog = lab_cache.get("prog") or {}
        c = pinlab.counts()
        lab_count.configure(text="%d running   %d shipped   %d killed   %d ideas"
                            % (c[pinlab.RUNNING], c[pinlab.SHIPPED],
                               c[pinlab.KILLED], c[pinlab.IDEA]))
        want = lab_which.get()
        order = {pinlab.RUNNING: 0, pinlab.IDEA: 1, pinlab.SHIPPED: 2,
                 pinlab.KILLED: 3, pinlab.PAUSED: 4}
        for e in sorted(pinlab.EXPERIMENTS, key=lambda x: order.get(x["status"], 9)):
            if want != "ALL" and e["status"] != want:
                continue
            lab_body.insert("end", "%s   " % e["name"], "name")
            lab_body.insert("end", "%s\n" % e["status"], e["status"])
            p = prog.get(e.get("match") or "", {})
            if p.get("settled"):
                lab_body.insert("end", "   SO FAR: %d settled, %d won, %d lost, %s%s\n"
                                % (p["settled"], p["won"], p["lost"], money(p["net"]),
                                   "" if p.get("running") else "   (not running now)"), "prog")
                w = lab_whatif(p.get("log"))
                if w:
                    pct = ("%+.1f%% on the money" % w["pct"]) if w.get("pct") is not None \
                        else ("%s" % money(w["diff"]))
                    sd = ("%+.0f%% swing" % w["sd_pct"]) if w.get("sd_pct") is not None \
                        else "swing not comparable yet"
                    lab_body.insert(
                        "end",
                        "   IF IT HAD BEEN LIVE since it started:  %s   %s\n"
                        % (pct, sd),
                        "whatif_good" if w["diff"] > 0 else "whatif_bad")
                    lab_body.insert(
                        "end",
                        "      it would have made %s where we actually made %s. "
                        "Worst single market %s against our %s.\n"
                        "      Scaled to the contracts we really traded, so this compares "
                        "the STRATEGY and not the stake (%d of its markets, %d of ours).\n"
                        % (money(w["arm_net"]), money(w["live_net"]),
                           money(w["arm_worst"]), money(w["live_worst"]),
                           w["n_arm"], w["n_live"]), "prog")
            elif e["status"] == pinlab.RUNNING:
                lab_body.insert("end", "   SO FAR: %s\n"
                                % ("running, nothing settled yet" if p.get("running")
                                   else "NOT RUNNING"), "prog")
            for label, k in (("WHAT IT DOES", "what"), ("WHY", "why"),
                             ("GOOD LOOKS LIKE", "good"), ("BAD LOOKS LIKE", "bad"),
                             ("WHAT TO WATCH", "watch"), ("WHAT HAPPENED", "outcome"),
                             ("WHAT IT WAS WORTH", "attribution"), ("WHERE IT IS", "where")):
                if e.get(k):
                    lab_body.insert("end", "   %s: " % label, "label")
                    lab_body.insert("end", "%s\n" % e[k])
            if e.get("since"):
                lab_body.insert("end", "   since %s\n" % e["since"], "prog")
            lab_body.insert("end", "\n")
        lab_body.tag_configure("name", font=("Segoe UI", 11, "bold"), foreground=C["text"])
        lab_body.tag_configure("label", font=("Segoe UI", 9, "bold"), foreground=C["muted"])
        lab_body.tag_configure("prog", foreground=C["watch"], font=("Segoe UI", 9))
        lab_body.tag_configure("whatif_good", foreground=C["gain"], font=("Segoe UI", 10, "bold"))
        lab_body.tag_configure("whatif_bad", foreground=C["loss"], font=("Segoe UI", 10, "bold"))
        lab_body.tag_configure(pinlab.RUNNING, foreground=C["gain"], font=("Segoe UI", 9, "bold"))
        lab_body.tag_configure(pinlab.SHIPPED, foreground=C["gain"], font=("Segoe UI", 9, "bold"))
        lab_body.tag_configure(pinlab.KILLED, foreground=C["loss"], font=("Segoe UI", 9, "bold"))
        lab_body.tag_configure(pinlab.IDEA, foreground=C["watch"], font=("Segoe UI", 9, "bold"))
        lab_body.tag_configure(pinlab.PAUSED, foreground=C["muted"], font=("Segoe UI", 9, "bold"))
        lab_body.configure(state="disabled")
        lab_menu_refresh()
        draw_lab_chart()

    # LOG tab
    log_tab = ttk.Frame(nb)
    nb.add(log_tab, text="  Log  ")
    section(log_tab, "WHAT THIS APP DID", "log")
    console = tk.Text(log_tab, height=8, bg=C["panel"], fg=C["text"], font=("Consolas", 10), relief="flat", wrap="word")
    console.pack(fill="x", padx=2)
    register(console, "log", "What this app did")
    section(log_tab, "THE BOT'S OWN CONSOLE (last lines) and THE WATCHDOG'S LOG", "log")
    tails = tk.Text(log_tab, bg=C["panel"], fg=C["muted"], font=("Consolas", 9), relief="flat", wrap="none")
    tails.pack(fill="both", expand=True, padx=2, pady=(0, 6))

    # HELP tab
    help_tab = ttk.Frame(nb)
    nb.add(help_tab, text="  Help  ")
    hf = tk.Frame(help_tab, bg=C["bg"])
    hf.pack(fill="both", expand=True, pady=(8, 6))
    help_txt = tk.Text(hf, bg=C["panel"], fg=C["text"], font=("Segoe UI", 10), relief="flat", wrap="word", padx=14, pady=10)
    hsb = ttk.Scrollbar(hf, orient="vertical", command=help_txt.yview)
    help_txt.configure(yscrollcommand=hsb.set)
    help_txt.pack(side="left", fill="both", expand=True)
    hsb.pack(side="left", fill="y")
    help_txt.tag_configure("h", font=("Segoe UI", 12, "bold"), foreground=C["blue"], spacing1=14, spacing3=4)
    help_txt.tag_configure("b", font=("Consolas", 10), foreground=C["text"])
    for key, title, body in HELP:
        help_txt.mark_set("sec_" + key, "end-1c")
        help_txt.mark_gravity("sec_" + key, "left")
        help_txt.insert("end", title + "\n", "h")
        help_txt.insert("end", body + "\n", "b")
    help_txt.configure(state="disabled")

    def show_help(key):
        nb.select(help_tab)
        try:
            help_txt.see("sec_" + key)
            idx = help_txt.index("sec_" + key)
            help_txt.yview_moveto(max(0.0, (float(idx.split(".")[0]) - 1) / float(help_txt.index("end").split(".")[0])))
        except tk.TclError:
            pass

    def console_log(msg):
        line = "%s  %s\n" % (et_str(time.time(), "%I:%M:%S %p"), msg)

        def _w():
            console.insert("end", line)
            console.see("end")
        root.after(0, _w)
        with open(os.path.join(RESULTS, "pindesk.log"), "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%dT%H:%M:%S") + "  " + msg + "\n")

    # ---- chart ----
    def chart_series():
        mode = ledger_mode = mode_var.get()
        rng = range_var.get()
        now = time.time()
        t_min = None
        if rng == "1":
            t_min = et_day_start(et_day(now))
        elif rng in ("3", "7", "30"):
            t_min = et_day_start(et_day(now - (int(rng) - 1) * 86400))
        if mode == "cum":
            pts, tot = [], 0.0
            for s in ledger.settled:
                if s["t"]:
                    tot += s["pnl"]
                    if t_min is None or s["t"] >= t_min:
                        # MONEY FIRST. The readout splits on the double space:
                        # everything before it becomes the big coloured number,
                        # the rest the grey line beside it. The operator asked
                        # for the price to be the visible part, not a small
                        # dark-grey afterthought.
                        pts.append((s["t"], tot, "$%+.2f  %s  %s, this bet %s" % (
                            tot, et_str(s["t"], "%a %b %d, %I:%M %p"), coin(s["tk"]),
                            money(s["pnl"]))))
            if t_min is not None and pts:
                base = pts[0][1] - 0.0
                _ = base
            return "line", pts, "$"
        if mode == "bank":
            pts = []
            for t, b, real in ledger.bank_series():
                if t_min is None or t >= t_min:
                    pts.append((t, b, "$%.2f  %s%s" % (
                        b, et_str(t, "%a %b %d, %I:%M %p"),
                        " -- a real balance reading" if real else " -- reconstructed between readings")))
            return "line", pts, "$"
        pts = []
        for d in ledger.days():
            ds = et_day_start(d)
            if t_min is not None and ds < t_min:
                continue
            s = Ledger.summary(ledger.settled_on(d))
            if mode == "day":
                pts.append((ds, s["net"], "$%+.2f  %s -- %d closes, %d lost, %s a close" % (
                    s["net"], et_str(ds, "%a %b %d"), s["closes"], s["lost"],
                    money(s["net"] / s["closes"]) if s["closes"] else "-")))
            else:
                b0 = ledger.bank_at(ds)
                r = (s["net"] / b0) if b0 else 0.0
                pts.append((ds, 100 * r, "%+.2f%%  %s -- on a bank of $%.2f that morning" % (
                    100 * r, et_str(ds, "%a %b %d"), b0 or 0)))
        return "bar", pts, ("$" if mode == "day" else "%")
        _ = ledger_mode

    def draw_chart():
        chart.delete("all")
        kind, pts, unit = chart_series()
        chart_pts["pts"], chart_pts["kind"] = pts, kind
        # THE HEADLINE, shown whenever the mouse is not on the chart.
        MODE_WORDS = {"cum": ("Money made, all time", "every settled market added up"),
                      "bank": ("Bank now", "what is in the account"),
                      "day": ("Best day", "money made on the strongest day in range"),
                      "daypct": ("Best day", "return on the bank that day")}
        if pts:
            last = pts[-1][1]
            if mode_var.get() in ("cum", "bank"):
                big = ("$%+.2f" % last) if mode_var.get() == "cum" else ("$%.2f" % last)
            else:
                best = max(pts, key=lambda p: p[1])
                big = ("$%+.2f" % best[1]) if mode_var.get() == "day" else ("%+.2f%%" % best[1])
            w = MODE_WORDS.get(mode_var.get(), ("", ""))
            chart_pts["headline"] = (big, "%s -- %s. Hover the chart for any single day."
                                     % (w[0], w[1]))
        else:
            chart_pts["headline"] = ("", "")
        chart_rest()
        if len(pts) < (2 if kind == "line" else 1):
            chart.create_text(20, 20, text="not enough data in this range yet", fill=C["muted"], anchor="w")
            return
        W = max(chart.winfo_width(), 200)
        H = max(chart.winfo_height(), 100)
        m = {"l": 64, "r": 16, "t": 16, "b": 26}
        vals = [v for _, v, _ in pts]
        lo = min(0.0, min(vals))
        hi = max(0.0, max(vals))
        if hi - lo < 1e-9:
            hi = lo + 1
        if kind == "line":
            t0, t1 = pts[0][0], pts[-1][0]
        else:
            t0, t1 = pts[0][0], pts[-1][0] + 86400

        def X(t):
            return m["l"] + (t - t0) / max(1, t1 - t0) * (W - m["l"] - m["r"])

        def Y(v):
            return m["t"] + (hi - v) / (hi - lo) * (H - m["t"] - m["b"])

        chart_pts["X"], chart_pts["Y"] = X, Y
        chart.create_line(m["l"], Y(0), W - m["r"], Y(0), fill=C["grey"], dash=(3, 3))
        for v in (lo, hi, 0.0):
            lab = ("$%.0f" % v) if unit == "$" else ("%.1f%%" % v)
            chart.create_text(m["l"] - 6, Y(v), text=lab, fill=C["muted"], anchor="e", font=("Segoe UI", 8))
        last = None
        for t, _v, _lab in pts:
            d = et_day(t)
            if d != last:
                x = X(t)
                chart.create_line(x, m["t"], x, H - m["b"], fill=C["panel2"])
                chart.create_text(x + 2, H - m["b"] + 10, text=d[5:], fill=C["muted"], anchor="w", font=("Segoe UI", 8))
                last = d
        if kind == "line":
            coords = []
            for t, v, _ in pts:
                coords += [X(t), Y(v)]
            chart.create_line(*coords, fill=C["gain"] if pts[-1][1] >= (pts[0][1] if mode_var.get() == "bank" else 0) else C["loss"], width=2)
            if mode_var.get() == "bank":
                for t, b, real in ledger.bank_series():
                    if real and pts[0][0] <= t <= pts[-1][0]:
                        chart.create_oval(X(t) - 3, Y(b) - 3, X(t) + 3, Y(b) + 3, fill=C["blue"], outline="")
            # the headline moved OUT of the chart corner and into the readout
            # above it, where it is 22pt instead of 12 and does not fight the
            # line for space.
        else:
            bw = max(4, (W - m["l"] - m["r"]) / max(1, len(pts)) * 0.7)
            for t, v, _ in pts:
                x = X(t + 43200)
                chart.create_rectangle(x - bw / 2, Y(v), x + bw / 2, Y(0), fill=C["gain"] if v >= 0 else C["loss"], outline="")
                chart.create_text(x, Y(v) - 8 if v >= 0 else Y(v) + 8, text=("%+.0f" % v) if unit == "$" else ("%+.1f%%" % v),
                                  fill=C["text"], font=("Segoe UI", 8))

    def chart_hover(e):
        chart.delete("hover")
        pts = chart_pts.get("pts") or []
        if not pts or "X" not in chart_pts:
            return
        X, Y = chart_pts["X"], chart_pts["Y"]
        if chart_pts["kind"] == "bar":
            best = min(pts, key=lambda p: abs(X(p[0] + 43200) - e.x))
            x, y = X(best[0] + 43200), Y(best[1])
        else:
            best = min(pts, key=lambda p: abs(X(p[0]) - e.x))
            x, y = X(best[0]), Y(best[1])
        chart.create_line(x, 0, x, chart.winfo_height(), fill=C["muted"], dash=(2, 2), tags="hover")
        chart.create_oval(x - 5, y - 5, x + 5, y + 5, fill=C["watch"], outline=C["panel"],
                          width=2, tags="hover")
        # the label goes to the fixed readout, not to a box under the cursor
        label = str(best[2])
        head, _, rest = label.partition("  ")
        ch_big.configure(text=head.strip() or label,
                         fg=(C["loss"] if head.strip().startswith("-") or "$-" in head
                             else C["gain"] if "$+" in head else C["text"]))
        ch_sub.configure(text=rest.strip())

    def chart_rest(_e=None):
        chart.delete("hover")
        d = chart_pts.get("headline") or ("", "")
        ch_big.configure(text=d[0], fg=(C["loss"] if "$-" in d[0] else
                                        C["gain"] if "$+" in d[0] else C["text"]))
        ch_sub.configure(text=d[1])

    chart.bind("<Motion>", chart_hover)
    chart.bind("<Leave>", chart_rest)
    chart.bind("<Configure>", lambda _e: draw_chart())

    # ---- rendering ----
    def render(h):
        state, hl, det, colour = status_of(h)
        banner.configure(bg=colour)
        head.configure(text=hl, bg=colour)
        sub.configure(text=det, bg=colour)
        clock.configure(text=et_now_str())
        now = time.time()
        today = et_day(now)
        yday = et_day(now - 86400)

        # chips
        q = h.get("quiet_s")
        v, s_ = chips["bot"]
        v.configure(text="alive" if h["alive"] else "not running", fg=C["gain"] if h["alive"] else C["loss"])
        s_.configure(text=("wrote %ds ago" % q) if q is not None else "")
        wd = h.get("watchdog_s")
        v, s_ = chips["wd"]
        ok = wd is not None and wd < 120
        v.configure(text="running" if ok else "NOT RUNNING", fg=C["gain"] if ok else C["loss"])
        s_.configure(text=("checked %ds ago" % wd) if wd is not None else "no heartbeat file")
        rec_ok = h["kalshi_ok"] and h["feeds_ok"]
        v, s_ = chips["rec"]
        v.configure(text="both writing" if rec_ok else "CHECK SYSTEM TAB", fg=C["gain"] if rec_ok else C["loss"])
        s_.configure(text="Kalshi %s, exchanges %s" % ("ok" if h["kalshi_ok"] else "STOPPED?", "ok" if h["feeds_ok"] else "STOPPED?"))
        dg = h.get("disk_gb")
        v, s_ = chips["disk"]
        v.configure(text=("%.1f GB" % dg) if dg is not None else "?",
                    fg=C["loss"] if dg is not None and dg < 6 else (C["watch"] if dg is not None and dg < 10 else C["text"]))
        s_.configure(text="tape stops below 5 GB")
        rg = h.get("ram_gb")
        v, s_ = chips["ram"]
        v.configure(text=("%.1f GB" % rg) if rg is not None else "?", fg=C["loss"] if rg is not None and rg < 1.5 else C["text"])
        s_.configure(text="")
        b = ledger.bank()
        dep = ledger.deposited()
        v, s_ = chips["bank"]
        v.configure(text=("$%.2f" % b["bank"]) if b else "?")
        if b and dep:
            s_.configure(text="%s on $%.2f put in (%.2fx)" % (pct((b["bank"] - dep) / dep), dep, b["bank"] / dep))
        v, s_ = chips["size"]
        v.configure(text=("%g contracts" % b["size"]) if b and b.get("size") else "?")
        s_.configure(text=("about $%.0f a bet" % (b["size"] * 0.97)) if b and b.get("size") else "")

        # tiles
        for key, rows, day in (("today", ledger.settled_on(today), today), ("yday", ledger.settled_on(yday), yday),
                               ("run", ledger.run_settled(), None), ("all", ledger.settled, None)):
            s = Ledger.summary(rows)
            v, p, sub_ = tile_vals[key]
            v.configure(text="$%+.2f" % s["net"], fg=C["gain"] if s["net"] >= 0 else C["loss"])
            if day:
                b0 = ledger.bank_at(et_day_start(day))
                r = (s["net"] / b0) if b0 else None
            elif key == "run" and ledger.last_start() and ledger.last_start()["t"]:
                b0 = ledger.bank_at(ledger.last_start()["t"])
                r = (s["net"] / b0) if b0 else None
            else:
                r = (s["net"] / dep) if dep else None
            p.configure(text=pct(r), fg=C["gain"] if (r or 0) >= 0 else C["loss"])
            lines = []
            if s["closes"]:
                lines.append("%d close%s (%d bet%s): %d won, %d lost (%.1f%%)" % (
                    s["closes"], "" if s["closes"] == 1 else "s", s["markets"], "" if s["markets"] == 1 else "s",
                    s["won"], s["lost"], s["loss_rate"]))
            else:
                lines.append("no settled bets yet")
            if day:
                fs = Ledger.fill_stats(ledger.fills_on(day))
                try:
                    up = hours_up_et_day(day, now if day == today else et_day_start(day) + 86400)
                except Exception:                        # noqa: BLE001
                    up = None
                lines.append("%d fills, %g contracts%s" % (fs["fills"], fs["contracts"],
                             ("  |  %.1f h up, $%.2f/h" % (up, s["net"] / up)) if up else ""))
            elif key == "all":
                if s["avg_win"] is not None and s["avg_loss"] is not None:
                    lines.append("avg win $%.2f, avg loss $%.2f: one loss = %.0f wins" % (s["avg_win"], s["avg_loss"], -s["avg_loss"] / max(0.01, s["avg_win"])))
            else:
                ls = ledger.last_start()
                if ls and ls["t"]:
                    lines.append("since %s" % et_str(ls["t"], "%m/%d %I:%M %p"))
            sub_.configure(text="\n".join(lines))

        # open bets
        rows = []
        opn = pinflat.positions(ledger.newest_rows) if h["alive"] else {}
        for tk_, n in opn.items():
            c = pinflat.close_epoch(tk_)
            sig = next((s for s in reversed(ledger.signals) if s["tk"] == tk_), None)
            paid = next((o["price"] for o in reversed(ledger.orders) if o["tk"] == tk_ and o["filled"] > 0), None)
            left = ("%d s" % max(0, c - now)) if c else "?"
            rows.append(((coin(tk_) + "  " + tk_.split("-")[-1], (sig or {}).get("want", "?").upper(),
                          "%g" % ledger.contracts_for(tk_), ("%.1fc" % (100 * paid)) if paid else "?",
                          close_et(tk_), left), "watch", sig))
        fill(tv_open, rows or [(("none", "", "", "", "", ""), "muted")])

        # settled
        rows = []
        for s in list(reversed(ledger.settled))[:80]:
            won = s["pnl"] >= 0
            rows.append(((et_str(s["t"], "%m/%d %I:%M %p") if s["t"] else "?", coin(s["tk"]), close_et(s["tk"]),
                          str(s["want"]).upper(), ("%.1fc" % (100 * float(s["cost"]))) if s["cost"] is not None else "?",
                          "%g" % ledger.contracts_for(s["tk"]), "WON" if won else "LOST", money(s["pnl"])),
                         "gain" if won else "loss", s))
        fill(tv_tr, rows)

        # signals -- each paired with ITS order (first unclaimed on the same ticker at/after it)
        rows = []
        recent_sig = list(reversed(ledger.signals))[:40]
        pool = ledger.orders[-400:]
        claimed = set()
        for s in reversed(recent_sig):
            s["_o"] = None
            for i, o in enumerate(pool):
                if i in claimed or o["tk"] != s["tk"] or not o["t"] or not s["t"] or o["t"] < s["t"] or o["t"] - s["t"] > 10:
                    continue
                claimed.add(i)
                s["_o"] = o
                break
        for s in recent_sig:
            o = s.get("_o")
            got = ("%g" % o["filled"]) if o else "-"
            tag = "gain" if (o and o["filled"] > 0) else ("muted" if o else "watch")
            rows.append(((et_str(s["t"], "%m/%d %I:%M:%S %p") if s["t"] else "?", coin(s["tk"]), close_et(s["tk"]),
                          str(s["want"]).upper(), "%.1fc" % (100 * float(s["price"] or 0)), "%+.2f" % float(s["edge_c"] or 0),
                          "%g" % float(s["take_n"] or s["size"] or 0), got), tag, s))
        fill(tv_sig, rows)

        # hedges
        rows = []
        for g in list(reversed(ledger.hedge_outcomes()))[:30]:
            ver = g["verdict"] or "pending"
            rows.append(((et_str(g["t"], "%m/%d %I:%M %p") if g["t"] else "?", coin(g["tk"]),
                          ("%.0f%%" % (100 * float(g["belief"]))) if g.get("belief") is not None else "?",
                          "%g" % float(g.get("n") or 0), ("%.0fc" % (100 * float(g["price"]))) if g.get("price") else "-",
                          ver, money(g["bet_pnl"]) if g["bet_pnl"] is not None else "-",
                          money(g["hedge_pnl"]) if g["hedge_pnl"] is not None else "-",
                          money(g["net"]) if g["net"] is not None else "-"),
                         "gain" if ver == "NEEDED" else ("muted" if ver == "pending" else "watch"), g))
        fill(tv_hg, rows or [(("none yet", "", "", "", "", "", "", "", ""), "muted")])

        # market
        act = ledger.activity()
        lvl = act["level"]
        mk_level.configure(text="SELLERS: %s" % lvl, fg={"QUIET": C["watch"], "BUSY": C["gain"], "NORMAL": C["text"]}.get(lvl, C["muted"]))
        if act["recent"] is not None:
            mk_desc.configure(text=("In the last four quarter-hours someone was selling the winning side on %.0f%% of looks.\n"
                                    "Over the whole record: a quiet quarter-hour is under %.0f%%, a typical one %.0f%%, a busy one over %.0f%%."
                                    % (100 * act["recent"], 100 * act["p25"], 100 * act["median"], 100 * act["p75"])))
        rows = []
        for c in list(reversed(ledger.closes))[:40]:
            share = Ledger.offer_share(c)
            what = ledger.reason(c)
            rows.append(((et_str(c["close"], "%m/%d %I:%M %p") if c["close"] else "?", "%d" % c["looks"],
                          pct(share, False) if share is not None else "-",
                          ("%+.2f" % c["best_edge_c"]) if c.get("best_edge_c") is not None else "-",
                          ("%.1fc" % (100 * c["best_price"])) if c.get("best_price") else "-",
                          ("%.0f" % c["depth_med"]) if c.get("depth_med") is not None else "-", what),
                         "gain" if c["fired"] else ("muted" if (share or 0) == 0 else "text"), c))
        fill(tv_mk, rows)
        cl_today = ledger.closes_on(today)
        fs_t = Ledger.fill_stats(ledger.fills_on(today))
        with_offer = sum(1 for c in cl_today if c["no_offer"] < c["looks"])
        passed_any = sum(1 for c in cl_today if c["tradeable"] > 0)
        mk_today.configure(text=("TODAY: %d quarter-hours watched, %d had somebody selling, %d had an offer that passed every rule, "
                                 "%d bought.  Orders sent %d, filled %d, lost races %d (someone took the offer first).  "
                                 "Asked for %g contracts, got %g (%s)."
                                 % (len(cl_today), with_offer, passed_any, sum(1 for c in cl_today if c["fired"]),
                                    fs_t["orders"], fs_t["fills"], fs_t["zero"], fs_t["asked"], fs_t["contracts"],
                                    pct(fs_t["share"], False) if fs_t["share"] is not None else "-")))

        # days
        rows = []
        lost_h = {}
        try:
            lost_h = lost_by_et_day()
        except Exception:                                # noqa: BLE001
            pass
        for d in reversed(ledger.days()):
            s = Ledger.summary(ledger.settled_on(d))
            fs = Ledger.fill_stats(ledger.fills_on(d))
            b0 = ledger.bank_at(et_day_start(d))
            r = (s["net"] / b0) if b0 else None
            try:
                up = hours_up_et_day(d, now if d == today else et_day_start(d) + 86400)
            except Exception:                            # noqa: BLE001
                up = None
            cl = ledger.closes_on(d)
            wo = sum(1 for c in cl if c["no_offer"] < c["looks"])
            rows.append(((d, money(s["net"]), pct(r), s["closes"], s["won"], s["lost"],
                          money(s["net"] / s["closes"]) if s["closes"] else "-", money(s["worst"]),
                          ("%.1f h" % up) if up else "-", ("$%.2f" % (s["net"] / up)) if up else "-",
                          fs["orders"], fs["fills"], fs["zero"], "%g" % fs["contracts"],
                          ("%.0f%%" % (100 * fs["median_pct"])) if fs["median_pct"] is not None else "-",
                          pct(fs["share"], False) if fs["share"] is not None else "-",
                          ("%d of %d" % (wo, len(cl))) if cl else "-"),
                         "gain" if s["net"] >= 0 else "loss", d))
            _ = lost_h
        fill(tv_days, rows)
        draw_chart()
        # redraw the Lab only when the worker has produced something new
        try:
            if lab_cache.get("at", 0) != lab_cache.get("drawn", -1):
                lab_cache["drawn"] = lab_cache.get("at", 0)
                draw_lab()
        except Exception:                                         # noqa: BLE001
            pass

        # losses
        rows = []
        tot_loss = 0.0
        for close, net, legs in ledger.losing_closes():
            coins = ", ".join(sorted({coin(l["tk"]) for l in legs}))
            paid = [float(l["cost"]) for l in legs if l["cost"] is not None]
            n = sum(ledger.contracts_for(l["tk"]) for l in legs)
            tot_loss += net
            rows.append(((et_str(close, "%m/%d %I:%M %p") if close else "?", et_day(close) if close else "?",
                          money(net), coins, len(legs), ("%.1fc" % (100 * sum(paid) / len(paid))) if paid else "?", "%g" % n),
                         "loss", (close, net, legs)))
        fill(tv_loss, rows or [(("no losing closes", "", "", "", "", "", ""), "muted")])
        s_all = Ledger.summary(ledger.settled)
        if s_all["closes"]:
            loss_sum.configure(text="%d losing closes out of %d (%.1f out of 100). They cost $%.2f in total against $%.2f won on the other %d."
                               % (s_all["lost"], s_all["closes"], s_all["loss_rate"], -tot_loss, s_all["net"] - tot_loss, s_all["won"]))

        # system
        ls = ledger.last_start() or {}
        rows = [
            (("Live bot", "The one that spends money: research\\pinrun.py --live. Buys the winning side in the last 30 s, hedges at belief < %s." % ls.get("hedge", "?"),
              "RUNNING" if h["alive"] else "DOWN", ("pid %s, wrote %ds ago" % (h["pid"], q)) if h["alive"] and q is not None else (h.get("flag") or "not running")),
             "gain" if h["alive"] else "loss"),
            (("Bot watchdog", "Relaunches the bot when it dies: 4 quick tries, then every 3 min for ever. Honours your PAUSE/STOP. watch_bot.ps1",
              "RUNNING" if ok else "DOWN", ("checked %ds ago" % wd) if wd is not None else "no heartbeat"), "gain" if ok else "loss"),
            (("Boot task", "Windows task KalsBoot: at sign-in and every 10 min, starts anything missing. boot_all.ps1",
              "installed", h.get("boot_last", "")[-70:]), "text"),
            (("Kalshi recorder", "Tapes Kalshi's feed: prices, trades, full order books, and the settlement index (1 print/s). One file per channel per hour. kalshi_collector.py",
              "WRITING" if h["kalshi_ok"] else "CHECK", "last full hour %.1f MB, %d channels open" % (h["kalshi_prev"] / 1e6, h["kalshi_open"])),
             "gain" if h["kalshi_ok"] else "loss"),
            (("Exchange recorder", "Tapes the order books of Coinbase, Kraken, Bitstamp and Gemini -- the exchanges behind the settlement index. crypto_feeds.py",
              "WRITING" if h["feeds_ok"] else "CHECK", "last full hour %.1f MB, %d feeds open" % (h["feeds_prev"] / 1e6, h["feeds_open"])),
             "gain" if h["feeds_ok"] else "loss"),
            (("Recorders' watchdog", "Restarts the two recorders if they die. run_all.ps1",
              "RUNNING" if h.get("run_all") else ("unknown" if h.get("run_all") is None else "DOWN"),
              "pid file logs\\run_all.pid" if h.get("run_all") else "no pid file yet (written on next start)"),
             "gain" if h.get("run_all") else "muted"),
            (("Crypto.com recorder", "Tapes Crypto.com's prediction markets every few seconds, for a possible second venue. cdc_record.py",
              "WRITING" if (h.get("cdc_age") is not None and h["cdc_age"] < 600) else "QUIET",
              ("wrote %ds ago" % h["cdc_age"]) if h.get("cdc_age") is not None else "no files"),
             "gain" if (h.get("cdc_age") is not None and h["cdc_age"] < 600) else "muted"),
            (("Paper arms", "Copies of the bot with one setting changed, pretending to trade, so a change is judged before it touches money.",
              "%d pin + %d race" % (h["paper_arms"], h["race_arms"]), "logs written in the last 15 min"), "text"),
            (("Phone link", "Telegram bot you message for status and controls; sends alerts on state changes and losses. research\\pinphone.py",
              "RUNNING" if (h.get("phone_s") is not None and h["phone_s"] < 120) else ("not set up" if not os.path.exists(os.path.join(KALS, "telegram.json")) else "DOWN"),
              ("polled %ds ago" % h["phone_s"]) if h.get("phone_s") is not None else "needs C:\\kals\\telegram.json (see pinphone.py)"),
             "gain" if (h.get("phone_s") is not None and h["phone_s"] < 120) else "muted"),
        ]
        fill(tv_sys, rows)
        sys_foot.configure(text="Disk %.1f GB free (tape stops below 5).  RAM %.1f GB free.  Hours lost to outages today: %.1f."
                           % (h.get("disk_gb") or 0, h.get("ram_gb") or 0, (lost_h or {}).get(today, 0.0)))

        # tails
        try:
            with open(os.path.join(RESULTS, "pinrun-live.out"), encoding="utf-8", errors="replace") as fh:
                bot_tail = fh.readlines()[-25:]
        except OSError:
            bot_tail = ["(no bot console yet)\n"]
        try:
            with open(os.path.join(RESULTS, "watch_bot.log"), encoding="utf-8", errors="replace") as fh:
                wd_tail = fh.readlines()[-8:]
        except OSError:
            wd_tail = ["(no watchdog log yet)\n"]
        tails.configure(state="normal")
        tails.delete("1.0", "end")
        tails.insert("end", "".join(bot_tail) + "\n---- watchdog ----\n" + "".join(wd_tail))
        tails.see("end")
        tails.configure(state="disabled")

    pending = {"h": None}

    def tick(force=False):
        def worker():
            try:
                ledger.refresh()
                pending["h"] = health(ledger)
                if time.time() - lab_cache.get("at", 0) > 45:
                    lab_cache["at"] = time.time()
                    lab_compute()
            except Exception:                            # noqa: BLE001
                with open(ERR_FILE, "a", encoding="utf-8") as fh:
                    fh.write(traceback.format_exc())
            root.after(0, apply)

        def apply():
            if pending["h"] is not None:
                try:
                    render(pending["h"])
                except Exception:                        # noqa: BLE001
                    with open(ERR_FILE, "a", encoding="utf-8") as fh:
                        fh.write(traceback.format_exc())
        threading.Thread(target=worker, daemon=True).start()

    def loop():
        tick()
        root.after(REFRESH_MS, loop)

    console_log("Pin Bot opened")
    try:                                   # PINDESK_TAB=n opens on a tab (used to screenshot each one)
        nb.select(int(os.environ.get("PINDESK_TAB", "0")))
    except (ValueError, tk.TclError):
        pass
    loop()
    root.mainloop()


# ===========================================================================
def selftest():
    import tempfile

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pindesk selftest: FAILED -- " + msg)

    ck(parse_t("2026-09-16T13:59:31Z") == calendar.timegm((2026, 9, 16, 13, 59, 31)), "ISO time parses")
    ck(parse_t(None) is None and parse_t("junk") is None, "NULL: junk time is None")
    e = calendar.timegm((2026, 9, 17, 3, 0, 0))
    ck(et_day(e) == "2026-09-16", "03:00Z on the 17th is still the 16th in ET")
    ck(et_str(e) == "11:00 PM", "and reads 11:00 PM")
    ck(et_day_start("2026-09-16") == calendar.timegm((2026, 9, 16, 4, 0, 0)), "an ET day starts at 04:00Z in September")
    ck(coin("KXBNB15M-26SEP161000-00") == "BNB" and coin("KXBTC15M-26SEP161000-00") == "BTC", "coin from ticker")
    ck(close_et("KXBNB15M-26SEP161000-00") == "10:00 AM", "the ticker clock is ET: 26SEP161000 closes 10:00 AM ET")
    ck(et_day(pinflat.close_epoch("KXXRP15M-26SEP170000-00")) == "2026-09-17",
       "THE OPERATOR'S CHECK: the midnight-ET XRP close belongs to the 17th, not the 16th")
    ck(_bank_from_why("bank $500.67") == 500.67 and _bank_from_why("bank $1,234.50") == 1234.5, "bank parses from the autosize reason")
    ck(_bank_from_why("size cap") is None, "NULL: no bank in the reason")
    ck(sort_key("$+1.75") < sort_key("$+15.04") and sort_key("98.0c") < sort_key("100.0c") and sort_key("-3.5%") < sort_key("2%"),
       "column sort reads numbers through $, +, c and %")
    ck(sort_key("BNB") > sort_key("$5") and sort_key("abc") < sort_key("xyz"), "text sorts after numbers, alphabetically")
    ck(pct(0.1234) == "+12.34%" and pct(None) == "-" and pct(0.5, False) == "50.00%", "percent formatting")

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "pinrun-live-20260916T135734Z.jsonl")
        c1 = "KXBNB15M-26SEP161000-00"          # closes 10:00 AM ET = 14:00Z
        c2 = "KXBTC15M-26SEP161000-00"          # SAME close
        c3 = "KXSOL15M-26SEP161015-15"          # 10:15 AM ET
        c4 = "KXETH15M-26SEP161030-30"          # 10:30 AM ET, hedged and the bet flipped
        c5 = "KXDOGE15M-26SEP161045-45"         # 10:45 AM ET, hedged and the bet held
        rows = [
            {"kind": "start", "t": "2026-09-16T13:00:00Z", "size": 20, "hedge_belief": 0.6, "tau_max": 30, "mode": "live"},
            {"kind": "autosize", "t": "2026-09-16T13:00:01Z", "old": 20, "new": 85, "why": "bank $500.00"},
            {"kind": "signal", "t": "2026-09-16T13:59:30Z", "ticker": c1, "want": "no", "price": 0.98, "edge_c": 1.5, "size": 85, "take_n": 85, "tau": 29},
            {"kind": "order", "t": "2026-09-16T13:59:31Z", "ticker": c1, "filled": 85.0, "exec_price": 0.979, "status": "executed", "body": {"count": "85.00"}},
            {"kind": "order", "t": "2026-09-16T13:59:35Z", "ticker": c2, "filled": 40.0, "exec_price": 0.97, "status": "executed", "body": {"count": "80.00"}},
            {"kind": "close_summary", "t": "2026-09-16T14:00:05Z", "close": calendar.timegm((2026, 9, 16, 14, 0, 0)), "looks": 1000, "no_offer": 600,
             "tradeable": 100, "fired": True, "gates": {"no_offer": 600, "edge_floor": 300}, "best_edge_c": 1.5, "best_price": 0.98, "depth": {"median": 120.0}},
            {"kind": "settled", "t": "2026-09-16T14:00:20Z", "ticker": c1, "want": "no", "result": "no", "cost": 0.979, "pnl_c": 166.26, "realised": 1.6626},
            {"kind": "settled", "t": "2026-09-16T14:00:21Z", "ticker": c2, "want": "no", "result": "yes", "cost": 0.97, "pnl_c": -3880.0, "realised": -37.1374},
            {"kind": "order", "t": "2026-09-16T14:14:35Z", "ticker": c3, "filled": 0.0, "status": "canceled", "body": {"count": "50.00"}},
            {"kind": "close_summary", "t": "2026-09-16T14:15:05Z", "close": calendar.timegm((2026, 9, 16, 14, 15, 0)), "looks": 1000, "no_offer": 1000,
             "tradeable": 0, "fired": False, "gates": {"no_offer": 1000}, "why": "decided but NOBODY OFFERED the winning side"},
            {"kind": "close_summary", "t": "2026-09-16T14:30:05Z", "close": calendar.timegm((2026, 9, 16, 14, 30, 0)), "looks": 1000, "no_offer": 900,
             "tradeable": 0, "fired": False, "gates": {"no_offer": 900, "price_ceiling": 100}},
            # hedged, bet flipped: entry YES lost, hedge NO won
            {"kind": "order", "t": "2026-09-16T14:29:35Z", "ticker": c4, "filled": 50.0, "exec_price": 0.97, "status": "executed", "body": {"count": "50.00"}},
            {"kind": "hedge", "t": "2026-09-16T14:29:50Z", "ticker": c4, "side": "no", "price": 0.5, "n": 50.0, "belief": 0.4, "entry": 0.97, "status": "executed"},
            {"kind": "settled", "t": "2026-09-16T14:30:20Z", "ticker": c4, "want": "yes", "result": "no", "cost": 0.97, "pnl_c": -4850.0, "realised": -85.6374},
            {"kind": "settled", "t": "2026-09-16T14:30:21Z", "ticker": c4, "want": "no", "result": "no", "cost": 0.5, "pnl_c": 2500.0, "realised": -60.6374},
            # hedged, bet held: entry won, hedge lost
            {"kind": "order", "t": "2026-09-16T14:44:35Z", "ticker": c5, "filled": 50.0, "exec_price": 0.97, "status": "executed", "body": {"count": "50.00"}},
            {"kind": "hedge", "t": "2026-09-16T14:44:50Z", "ticker": c5, "side": "no", "price": 0.3, "n": 10.0, "belief": 0.55, "entry": 0.97, "status": "executed"},
            {"kind": "settled", "t": "2026-09-16T14:45:20Z", "ticker": c5, "want": "yes", "result": "yes", "cost": 0.97, "pnl_c": 500.0, "realised": -55.6374},
            {"kind": "settled", "t": "2026-09-16T14:45:21Z", "ticker": c5, "want": "no", "result": "yes", "cost": 0.3, "pnl_c": -300.0, "realised": -58.6374},
            {"kind": "halt", "t": "2026-09-16T15:30:00Z", "why": "loss COUNT brake: 2 losing trades this run >= 2"},
        ]
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows[:-1]:
                fh.write(json.dumps(r) + "\n")
            fh.write('{"kind": "close_summary", "t": "2026-09-16T10:1')      # cut off mid-line
        # point the Kalshi ledger at a path that does not exist, so this half
        # of the test cannot accidentally read the real account's books
        import pinledger as _pl
        _sv = _pl.LEDGER
        _pl.LEDGER = os.path.join(td, "no-such-ledger.json")
        L = Ledger(results=td)
        ck(L.refresh(), "first refresh reads the file")
        ck(len(L.settled) == 0,
           "SETTLED MONEY NO LONGER COMES FROM THE LOGS. The logs hold one line "
           "PER LEG, so a hedged market appeared as two trades and one of them "
           "as a pure loss -- KXDOGE15M-26SEP180015-15 was shown as -$3.93 (the "
           "11c hedge leg alone) on a market Kalshi settled at +$4.36")
        ck(len(L.orders) == 5 and len(L.signals) == 1 and len(L.hedges) == 2 and len(L.closes) == 3,
           "everything that explains WHY we traded is still read from the logs")
        # ...and the money comes from Kalshi's books, ONE ROW PER MARKET
        _lg = os.path.join(td, "kalshi_ledger.json")
        _pl.LEDGER = _lg
        try:
            with open(_lg, "w", encoding="utf-8") as _fh:
                json.dump({"settlements": {"k1": {
                    "ticker": "KXDOGE15M-26SEP180015-15", "market_result": "no",
                    "yes_count_fp": "33.63", "yes_total_cost_dollars": "3.699300",
                    "no_count_fp": "33.63", "no_total_cost_dollars": "24.886200",
                    "revenue": 0, "fee_cost": "0.683500",
                    "settled_time": "2026-09-18T04:15:04Z"}}}, _fh)
            L2 = Ledger(results=td)
            L2._kalshi_mtime = None
            L2.refresh()
            if not L2.settled:          # same-second mtime on a fast disk
                L2._kalshi_mtime = None
                L2._load_kalshi()
            ck(len(L2.settled) == 1,
               "a market we HEDGED is ONE row, not two legs")
            ck(abs(L2.settled[0]["pnl"] - 4.36) < 0.01,
               "and it carries Kalshi's own net (+$4.36), not the losing leg")
            ck(L2.settled[0]["hedged"] is True and L2.settled[0]["book"] == "crypto",
               "it is marked as hedged and attributed to the right book")
        finally:
            # back to a path that does NOT exist -- restoring the real one here
            # would let the rest of this test read the live account's books
            _pl.LEDGER = os.path.join(td, "no-such-ledger.json")
        ck(L.halts == [], "the truncated tail line is not read, and nothing after it is")
        # RULE 4 STILL APPLIES, on Kalshi rows now: several MARKETS share one
        # close, and a day is counted in closes. Built directly, because the
        # money no longer comes from the log this Ledger just read.
        L.settled = [
            {"t": calendar.timegm((2026, 9, 16, 14, 0, 20)), "tk": c1,
             "pnl": 1.6626, "close": calendar.timegm((2026, 9, 16, 14, 0, 0)),
             "want": "no", "result": "no", "cost": 0.979, "book": "crypto"},
            {"t": calendar.timegm((2026, 9, 16, 14, 0, 21)), "tk": c2,
             "pnl": -38.80, "close": calendar.timegm((2026, 9, 16, 14, 0, 0)),
             "want": "yes", "result": "no", "cost": 0.97, "book": "crypto"},
            {"t": calendar.timegm((2026, 9, 16, 14, 30, 20)), "tk": c4,
             "pnl": -25.00, "close": calendar.timegm((2026, 9, 16, 14, 30, 0)),
             "want": "yes", "result": "no", "cost": 0.97, "book": "crypto"},
            {"t": calendar.timegm((2026, 9, 16, 14, 45, 20)), "tk": c5,
             "pnl": +5.00, "close": calendar.timegm((2026, 9, 16, 14, 45, 0)),
             "want": "no", "result": "no", "cost": 0.30, "book": "crypto"},
        ]
        s = Ledger.summary(L.settled)
        ck(s["closes"] == 3,
           "three CLOSES from four markets -- two of them settled on the same "
           "quarter hour and are one observation, not two (rule 4)")
        ck(s["lost"] == 2 and s["won"] == 1,
           "the shared close lost as a whole; so did one other; one won")
        ck(abs(s["net"] - (1.6626 - 38.80 - 25.00 + 5.00)) < 1e-6,
           "and the net is every market's own P&L added up")
        ck(s["avg_win"] is not None and s["avg_loss"] is not None and s["avg_loss"] < 0 < s["avg_win"], "average win and loss are signed the right way")
        ck(L.settled_on("2026-09-15") == [] and L.settled_on("2026-09-17") == [], "nothing leaks into the neighbouring ET days")
        fs = Ledger.fill_stats(L.orders)
        ck(fs["orders"] == 5 and fs["fills"] == 4 and fs["zero"] == 1 and fs["contracts"] == 225.0 and fs["asked"] == 315.0
           and abs(fs["share"] - 225.0 / 315.0) < 1e-9, "fill stats: fills, lost races, contracts asked vs got")
        ck(L.bank()["bank"] == 500.0 and L.bank()["size"] == 85, "bank and size from the last autosize")
        ck(L.deposited() == 500.0, "nothing settled before the first reading, so deposited = first reading")
        with open(os.path.join(td, "DEPOSITED.txt"), "w") as fh:
            fh.write("$450.00  (what I actually put in)\n")
        ck(L.deposited() == 450.0, "results\\DEPOSITED.txt overrides the reconstruction with the operator's own figure")
        os.remove(os.path.join(td, "DEPOSITED.txt"))
        # bank_at walks the bank reading forward through settlements. Give it
        # two of its own, since the money no longer arrives from the log.
        _keep = L.settled
        L.settled = [
            {"t": calendar.timegm((2026, 9, 16, 14, 0, 20)), "tk": c1,
             "pnl": 1.6626, "close": 100, "book": "crypto"},
            {"t": calendar.timegm((2026, 9, 16, 14, 0, 50)), "tk": c2,
             "pnl": -38.80, "close": 100, "book": "crypto"},
        ]
        ck(abs(L.bank_at(calendar.timegm((2026, 9, 16, 14, 1, 0))) - (500.0 + 1.6626 - 38.80)) < 1e-6,
           "bank at 14:01Z = reading + the two settlements since")
        ck(abs(L.bank_at(calendar.timegm((2026, 9, 16, 4, 0, 0))) - 500.0) < 1e-6,
           "bank at the ET day start (before the first reading) falls back to deposited + settlements so far")
        L.settled = _keep
        # The hedge verdict now reads the MARKET, because Kalshi settles a
        # hedged market as one row. Give it two markets to read.
        _k2 = L.settled
        L.settled = [
            # c4: the hedge bought NO and NO won -> the original bet flipped
            {"t": 1, "tk": c4, "pnl": -23.50, "close": 100, "result": "no", "book": "crypto"},
            # c5: the hedge bought NO and YES won -> the original bet held
            {"t": 2, "tk": c5, "pnl": +2.00, "close": 300, "result": "yes", "book": "crypto"},
        ]
        ho = L.hedge_outcomes()
        ck(len(ho) == 2, "one entry per hedged market, however many tries it took")
        by = {h["tk"]: h for h in ho}
        ck(by[c4]["verdict"] == "NEEDED" and abs(by[c4]["net"] + 23.50) < 1e-9,
           "the hedge bought NO and NO won -> NEEDED; the market netted -$23.50 "
           "and would have been worse unhedged")
        ck(by[c5]["verdict"] == "WASTED" and abs(by[c5]["net"] - 2.00) < 1e-9,
           "the hedge bought NO and YES won -> WASTED; the market still netted "
           "+$2.00 because the original bet carried it")
        L.settled = _k2
        act = L.activity(last_n=2)
        ck(act["level"] in ("QUIET", "NORMAL", "BUSY") and act["recent"] is not None, "activity level is one of three words")
        ck(Ledger.why_no_trade(L.closes[0]) == "BOUGHT", "a fired close says BOUGHT")
        ck(Ledger.why_no_trade(L.closes[1]) == GATE_WORDS["no_offer"], "nobody offered -> says so in words")
        ck(Ledger.why_no_trade(L.closes[2]) == GATE_WORDS["price_ceiling"], "the biggest non-empty gate is named (price cap)")
        ck(abs(Ledger.offer_share(L.closes[0]) - 0.4) < 1e-9, "offered = 1 - no_offer/looks")
        ck(L.days() == ["2026-09-16"], "one ET day")
        ck(L.contracts_for(c2) == 40.0, "contracts per ticker from orders")
        ck(len(L.losing_closes()) == 2, "the losses ledger holds the two losing closes")
        # stories, in words
        won_story = story_settled(L, [s for s in L.settled if s["tk"] == c1][0])
        ck("WHAT IT SAW" in won_story and "WHAT IT DID" in won_story and "HOW IT WENT" in won_story
           and "bought 85 contracts at 97.9c" in won_story and "the side it held" in won_story,
           "a winning bet's story has what it saw, did, and how it went")
        lost_story = story_settled(L, [s for s in L.settled if s["tk"] == c2][0])
        ck("AGAINST the side it held" in lost_story and "$-38.80" in lost_story, "a losing bet's story says so, with the money")
        hedged_story = story_settled(L, [s for s in L.settled if s["tk"] == c4 and s["want"] == "yes"][0])
        ck("INSURANCE" in hedged_story and "NEEDED" in hedged_story, "a hedged bet's story carries the insurance verdict")
        # There is no longer a separate "hedge leg" row to tell a story about:
        # Kalshi settles a hedged market as ONE row, which is the honest unit
        # and the whole reason the tool stopped reporting -$3.93 on a market
        # that made +$4.36.
        ck(not [x for x in L.settled if x["tk"] == c4 and x["want"] == "no"],
           "a hedged market has ONE row, so there is no orphan insurance leg "
           "masquerading as its own losing trade")
        hs = story_hedge(L, ho[0])
        ck("belief" in hs and ho[0]["verdict"] in hs,
           "a hedge's story still says why it fired and how it went")
        cs = story_close(L, L.closes[1])
        ck("nobody was selling" in cs and "no trade" in cs, "a quiet quarter-hour's story says nobody was selling")
        ck("bought 125 contracts" in story_close(L, L.closes[0]), "a bought quarter-hour's story says how many")
        ds = story_day(L, "2026-09-16", now=calendar.timegm((2026, 9, 17, 12, 0, 0)))
        ck("MONEY" in ds and "$500.00" in ds and "3 closes" in ds and "1 were lost races" in ds, "a day's story: money, bets, sellers")
        ss = story_signal(L, L.signals[0])
        ck("bought 85 contracts" in ss and "WON" in ss, "a signal's story pairs it with its order and outcome")
        ls_ = story_loss(L, *L.losing_closes()[0])
        ck("lost $" in ls_ and "WHY IT HURTS" in ls_, "a loss story lists the legs and why it matters")
        with open(p, "a", encoding="utf-8") as fh:
            fh.write("\n" + json.dumps(rows[-1]) + "\n")
        _before = len(L.settled)
        ck(L.refresh() and len(L.halts) == 1 and len(L.settled) == _before,
           "an appended LOG record is picked up incrementally, and it does not "
           "touch the settled money -- that comes from Kalshi and only changes "
           "when the ledger file does")
        ck(not L.refresh(), "NULL: nothing new -> nothing read")
        _pl.LEDGER = _sv

        base = {"pid": 1, "alive": True, "flag": None, "quiet_s": 30, "watchdog_s": 10, "open": {}, "halt": None}
        ck(status_of(dict(base))[0] == "TRADING", "alive, quiet 30 s, no flag -> TRADING")
        ck(status_of(dict(base, quiet_s=30 * 60))[0] == "STALE", "alive but silent 30 min -> STALE")
        ck(status_of(dict(base, flag="operator PAUSE", open={c3: 1}))[0] == "PAUSING", "alive + flag + open bet -> PAUSING")
        ck(status_of(dict(base, alive=False, flag="operator PAUSE at x"))[0] == "PAUSED", "dead + pause flag -> PAUSED")
        ck(status_of(dict(base, alive=False, flag="operator STOP at x"))[0] == "STOPPED", "dead + stop flag -> STOPPED")
        h = dict(base, alive=False, halt={"kind": "halt", "t": time.time() - 60, "why": rows[-1]["why"]})
        ck(status_of(h)[0] == "BRAKE" and "restarts in" in status_of(h)[2], "dead after a money brake -> BRAKE, with the countdown")
        ck(status_of(dict(base, alive=False))[0] == "DOWN" and "bringing it back" in status_of(dict(base, alive=False))[1],
           "dead, watchdog alive -> DOWN, watchdog restarting")
        ck("watchdog is not running" in status_of(dict(base, alive=False, watchdog_s=None))[1],
           "dead, no watchdog heartbeat -> says so")
        ev = status_of(dict(base, flag="operator PAUSE at x"))[2]
        ck("is OPEN (alive)" in ev and "30 s ago" in ev and "flag PRESENT" in ev,
           "the banner carries its evidence: the process was opened, the log age, the flag on disk")
        ck("is NOT running" in status_of(dict(base, alive=False))[2] and "flag absent" in status_of(dict(base, alive=False))[2],
           "...and says NOT running when the pid could not be opened")
    ck(all(k for k, _t, _b in HELP) and len({k for k, _t, _b in HELP}) == len(HELP), "help sections have unique keys")
    print("pindesk selftest: OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return 0
    try:
        run_gui()
    except Exception:                                    # noqa: BLE001
        with open(ERR_FILE, "a", encoding="utf-8") as fh:
            fh.write("%s\n%s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), traceback.format_exc()))
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
