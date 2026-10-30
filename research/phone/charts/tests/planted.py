"""planted.py -- the planted data every chart test draws from (no file, no network): a pindesk.Ledger with ten days of
quarter-hours, the main account's Kalshi ledger file, and a botstats cache + process table for every pot.

v-tg-rebuild step 8 (2026-10-30): moved out of tgcharts.selftest (one 340-line function) unchanged, so each test module
can plant its own copy.
"""
import calendar
import contextlib
import json
import os
import tempfile
import time
import types

import pindesk
from pindesk import Ledger
from phone.charts.base import MAX_BYTES

NOW = calendar.timegm((2026, 10, 18, 15, 30, 0))                   # 11:30 AM ET Sun Oct 18


def ck(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg, flush=True)
    if not cond:
        raise SystemExit("tgcharts selftest: FAILED -- " + msg)


def is_png(x):
    return isinstance(x, tuple) and x[0][:8] == b"\x89PNG\r\n\x1a\n" and 1000 < len(x[0]) < MAX_BYTES and x[1]


def px_count(png_, hexc):
    """How many pixels of the PNG are colour `hexc` (within 2%)."""
    import io
    import matplotlib.image as _mi
    a_ = _mi.imread(io.BytesIO(png_))[:, :, :3]
    want_ = [int(hexc[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return int((abs(a_ - want_) < 0.02).all(axis=2).sum())


def same_picture(a, b, levels=24, pixels=2000):
    """Two PNGs show the same picture: identical, or (golden/README 'render noise') at most `pixels` pixels differ by
    at most `levels` of 255."""
    if a == b:
        return True
    import io
    import matplotlib.image as _mi
    x, y = _mi.imread(io.BytesIO(a)), _mi.imread(io.BytesIO(b))
    if x.shape != y.shape:
        return False
    d = (abs(x - y) * 255.0).max(axis=2)
    return int((d > 0.5).sum()) <= pixels and float(d.max()) <= levels


def planted_ledger(now=NOW):
    """ten days of quarter-hours: a settle each (every 37th lost $4), an order each (every 5th filled nothing), a close
    summary each, a bank read every 3 hours, a hedge every 50th, a $200 deposit 3 days ago; 'deposited' $1,000."""
    led = Ledger(results=tempfile.gettempdir())
    led.deposited = lambda: 1000.0
    st, ords, auto, closes, hed = [], [], [], [], []
    for k in range(10 * 96):                                          # ten days of quarter-hours
        c = now - k * 900 - 60
        pnl = -4.0 if k % 37 == 5 else 0.6
        tk = "KXBTC15M-26OCT%02d%02d%02d-00" % (18, 0, 0)
        st.append({"t": c + 30, "tk": "%s-%d" % (tk, k), "pnl": pnl, "close": c, "result": "yes", "want": "yes", "file": "kalshi"})
        ords.append({"t": c - 30, "tk": "%s-%d" % (tk, k), "filled": 0.0 if k % 5 == 0 else 10.0, "asked": 10.0,
                     "price": 0.96, "ask_seen": 0.96, "limit_sent": 0.97, "tau": 25, "close": c})
        closes.append({"t": c, "close": c, "looks": 100, "no_offer": 40 + (k % 30), "fired": k % 3 == 0, "gates": {}})
        if k % 12 == 0:
            auto.append({"t": c, "bank": 1000.0 + 0.5 * (960 - k), "size": 20})
        if k % 50 == 7:
            hed.append({"t": c - 20, "kind": "hedge", "tk": "%s-%d" % (tk, k), "status": "executed", "side": "no", "n": 5,
                        "price": 0.1, "belief": 0.6})
    led.settled = sorted(st, key=lambda s: s["t"])
    led.orders = sorted(ords, key=lambda o: o["t"])
    led.autosize = sorted(auto, key=lambda a: a["t"])
    led.closes = sorted(closes, key=lambda c: c["close"])
    led.hedges = hed
    led.external = [{"t": now - 3 * 86400, "move": "deposit", "amount": 200.0}]
    return led


def empty_ledger():
    empty = Ledger(results=tempfile.gettempdir())
    empty.deposited = lambda: None
    return empty


def planted_pp():
    """A stand-in for the pinphone module with no botstats (no _bs): every botstats picture falls back."""
    return types.SimpleNamespace(FIRST_LIVE_DAY="2026-10-09", window_stats=None)


@contextlib.contextmanager
def kalshi_ledger_file(led, now=NOW):
    """The main account's Kalshi ledger (200 hourly markets, every 25th lost, every 40th hedged) written to a temp
    folder that becomes led.results, and pinledger.load_cache serving the same rows. Yields the pinphone module."""
    import pinphone as PP
    import pinledger
    with tempfile.TemporaryDirectory() as td:
        rows = []
        for k in range(200):
            c = now - k * 3600
            tm = time.strftime("%y%b%d%H%M", time.gmtime(c + pindesk.et_offset(c))).upper()   # v-etclock: ET, not a fixed -4 h
            win = k % 25 != 3
            hedged = k % 40 == 0
            rows.append({"ticker": "KXBTC15M-%s-00" % tm, "settled_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(c + 60)),
                         "market_result": "yes" if win else "no", "yes_count_fp": "10.00", "no_count_fp": "10.00" if hedged else "0.00",
                         "yes_total_cost_dollars": "9.60", "no_total_cost_dollars": "1.00" if hedged else "0.0000",
                         "fee_cost": "0.07", "revenue": 1000 if win else 0, "value": 100 if win else 0})
        with open(os.path.join(td, PP.pinday.LEDGER_NAME), "w", encoding="utf-8") as fh:
            json.dump({"rows": {"%s|%s" % (r["ticker"], r["settled_time"]): r for r in rows}}, fh)
        old_results = led.results
        led.results = td
        sv = pinledger.load_cache
        try:
            pinledger.load_cache = lambda path=None: {"%s|%s" % (r["ticker"], r["settled_time"]): r for r in rows}
            yield PP
        finally:
            pinledger.load_cache = sv
            led.results = old_results


class NoBS:
    """The pinphone module with botstats unreadable (_bs raises): /stats falls back to the main account."""

    def __init__(self, pp):
        self._pp = pp

    def __getattr__(self, k):
        if k == "_bs":
            raise RuntimeError("botstats cannot be read (planted)")
        return getattr(self._pp, k)


FX_PROC = (5, "x", "python research/cleanroom/fxtake_live.py --subaccount 5 --fx-subaccount 4 --live")
FUNDS_WHAT = {4: {0: "FX taker: the 5 currency pairs", 2: "coin-race reward test (stopped)"}}


@contextlib.contextmanager
def planted_botstats(now=NOW, fx=False):
    """botstats with a planted cache (every pot: main account 300 markets with every 3rd a coin race leg, 1 ladder 40,
    2 forecaster 60, 3 weather 20, 4 the FX pairs 12 (its first row the old reward test's), 5 commodities 30; every 19th
    lost), money moved in, and a process table with the pin bot, the race, the forecaster and the ladder running (and
    the FX taker when fx=True). The weather bot's stop file is set. Yields (botstats, cache, procs list, results dir,
    the old-style ctx dict)."""
    import botstats as BS
    import pinphone as PP
    with tempfile.TemporaryDirectory() as td:
        sv = (BS.RESULTS, BS._load)
        try:
            BS.RESULTS = td
            open(os.path.join(td, BS.SPEC["weather"]["stop"]), "w", encoding="utf-8").close()   # weather: stopped
            subs = {}
            for sub, n in (("0", 300), ("1", 40), ("2", 60), ("3", 20), ("4", 12), ("5", 30)):
                r = {}
                for k in range(n):
                    t = now - k * 4000
                    tk = ("KXBTC15M-26OCT%02d%02d%02d-%02d" % (18, k % 24, 0, k % 60)) if sub == "0" else "KXX-%s-%d" % (sub, k)
                    if sub == "4":                       # the currency pairs; its first row is the old reward test's
                        tk = "KXUSDJPY15M-26OCT18%04d-30" % k if k else "KXBTC15M-26OCT180000-00"
                    if sub == "5":
                        tk = "KXGOLD15M-26OCT18%04d-45" % k
                    if sub == "0" and k % 3 == 0:
                        tk = "KXCRYPTOLEAD15M-26OCT18%04d-%s" % (k, ("BTC", "ETH")[k % 2])
                    win = k % 19 != 4
                    r["%s|%d" % (tk, k)] = {"ticker": tk, "settled_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)),
                                            "market_result": "yes" if win else "no", "yes_count_fp": "5.00", "no_count_fp": "0.00",
                                            "yes_total_cost_dollars": "4.80", "no_total_cost_dollars": "0.00", "fee_cost": "0.03",
                                            "revenue": 500 if win else 0, "value": 100 if win else 0}
                subs[sub] = {"rows": r, "complete": True, "tried": now, "fetched": now, "positions": [], "pos_t": now,
                             "balance": 100.0, "bal_t": now}
            c = {"subs": subs, "ledgers": {"tried": now, "fetched": now,
                                           "deposits": [{"amount_cents": 150000, "fee_cents": 0, "status": "applied",
                                                         "created_ts": int(now - 20 * 86400), "finalized_ts": int(now - 20 * 86400)}],
                                           "withdrawals": [],
                                           "transfers": [{"amount_cents": 10000, "from_subaccount": 0, "to_subaccount": s,
                                                          "exchange_index": BS.SUB_POOL[str(s)],
                                                          "created_ts": int(now - 15 * 86400)} for s in (1, 2, 3, 4, 5)]
                                           + [{"amount_cents": 5500, "from_subaccount": 0, "to_subaccount": 4, "exchange_index": 2,
                                               "created_ts": int(now - 18 * 86400)}],
                                           "subaccount_balances": [{"subaccount_number": int(s), "exchange_index": BS.SUB_POOL[s],
                                                                    "balance": 100.0} for s in BS.SUBS]}}
            procs = [(1, "x", "python research/pinrun.py --live"), (2, "x", "python research/pinracearm.py --live"),
                     (3, "x", "python research/forecaster_live.py --live"), (4, "x", "python research/ladder_live.py --live")]
            if fx:
                procs.append(FX_PROC)
            BS._load = lambda now_, getter, procs_: (c, BS._norm_procs(procs), True)
            ctx3 = {"now": now, "pp": PP, "funds_what": FUNDS_WHAT}
            yield BS, c, procs, td, ctx3
        finally:
            BS.RESULTS, BS._load = sv
