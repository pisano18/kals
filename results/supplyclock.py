"""supplyclock.py -- where cheap crypto supply sits on the clock (TAPE SHAPE ONLY).

Streams the trade tape hour by hour; aggregates per (tau band, price band) on
the fly; never holds rows. Does NOT import replay.py or pinattrib.py
(pinattrib imports the live bot). load_outcomes is copied from pinattrib.

Everything here is what the MARKET did. It is never our loss rate (rule 5).
"""
import calendar
import collections
import datetime as dt
import glob
import gzip
import json
import os
import sys
import time

sys.path.insert(0, r"C:\kals-repo\research")
import pinflat  # noqa: E402  (stdlib-only module; close_epoch from ticker)

DATA = r"C:\kals\kalshi_data\trade"
SETTLE = r"C:\kals\fulltape\markets.json"
SERIES = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
          "KXBNB15M", "KXHYPE15M", "KXNEAR15M", "KXZEC15M")
FEE_RATE = 0.07
TAU_BANDS = ((0, 5), (6, 15), (16, 30), (31, 45), (46, 60), (61, 90),
             (91, 120), (121, 180))
PX_BANDS = ((0.90, 0.93), (0.93, 0.95), (0.95, 0.97), (0.97, 0.98))
ET_OFF = -4 * 3600   # September = EDT


def fee(p):
    return FEE_RATE * p * (1.0 - p)


def break_even(p):
    w = (1.0 - p) - fee(p)
    l = p + fee(p)
    return 100.0 * w / (w + l) if w > 0 else 0.0


def _result_word(res):
    if isinstance(res, str):
        r = res.strip().lower()
        return r if r in ("yes", "no") else None
    if isinstance(res, bool):
        return "yes" if res else "no"
    if isinstance(res, (int, float)):
        if float(res) == 1.0:
            return "yes"
        if float(res) == 0.0:
            return "no"
    return None


def load_outcomes(markets_json=SETTLE):
    out = {}
    paths = [markets_json]
    base = os.path.dirname(markets_json)
    paths += sorted(glob.glob(os.path.join(base + "_*", "markets.json")))
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        for _ser, rows in (d or {}).items():
            for r in rows or []:
                res = _result_word(r.get("result"))
                if res and r.get("ticker"):
                    out[r["ticker"]] = res
    return out


def tau_band(t):
    for lo, hi in TAU_BANDS:
        if lo <= t <= hi:
            return (lo, hi)
    return None


def px_band(p):
    # half-open so a 93.0c print lands in ONE band; last band closed at 98c
    for lo, hi in PX_BANDS:
        if lo <= p < hi:
            return (lo, hi)
    if abs(p - 0.98) < 1e-9:
        return PX_BANDS[-1]
    return None


def new_cell():
    return {"w_closes": set(), "w_mkts": set(), "w_trades": 0, "w_contracts": 0.0,
            "a_closes": set(), "a_mkts": set(), "a_lost_closes": set(),
            "a_lost_mkts": set(), "a_trades": 0, "a_lost_trades": 0,
            "a_contracts": 0.0, "a_paid_x_n": 0.0}


class Agg:
    def __init__(self):
        self.cells = collections.defaultdict(new_cell)          # pooled
        self.btc = collections.defaultdict(new_cell)            # BTC alone
        self.day = collections.defaultdict(lambda: collections.defaultdict(float))
        self.day_closes = collections.defaultdict(lambda: collections.defaultdict(set))
        self.unjoined = collections.defaultdict(set)   # et_day -> tickers w/o settlement
        self.joined = collections.defaultdict(set)     # et_day -> tickers w/ settlement
        self.trades_seen = 0

    def add(self, ser, tau, paid, won, n, close, mkt, ts):
        tb = tau_band(tau)
        pb = px_band(paid)
        if tb is None or pb is None:
            return
        for table in ((self.cells, True), (self.btc, ser == "KXBTC15M")):
            d, use = table
            if not use:
                continue
            c = d[(tb, pb)]
            c["a_closes"].add(close); c["a_mkts"].add(mkt)
            c["a_trades"] += 1; c["a_contracts"] += n; c["a_paid_x_n"] += paid
            if won:
                c["w_closes"].add(close); c["w_mkts"].add(mkt)
                c["w_trades"] += 1; c["w_contracts"] += n
            else:
                c["a_lost_closes"].add(close); c["a_lost_mkts"].add(mkt)
                c["a_lost_trades"] += 1
        if won and 0 <= tau <= 120:
            et_day = dt.datetime.fromtimestamp(ts + ET_OFF, dt.UTC).strftime("%m-%d")
            key = "0-30" if tau <= 30 else ("31-60" if tau <= 60 else "61-120")
            self.day[et_day][key] += n
            self.day_closes[et_day][key].add(close)
            if ser == "KXBTC15M":
                self.day[et_day]["btc " + key] += n


def walk(files, settled, agg):
    torn, truncated = 0, 0
    t0 = time.time()
    for i, f in enumerate(files):
        lines_before = agg.trades_seen
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '15M-' not in line:
                        continue
                    try:
                        m = json.loads(line).get("msg") or {}
                    except ValueError:
                        continue
                    tk = m.get("market_ticker") or ""
                    ser = tk.split("-", 1)[0]
                    if ser not in SERIES:
                        continue
                    close = pinflat.close_epoch(tk)
                    if close is None:
                        continue
                    try:
                        ts = int(m["ts"])
                        yes_px = float(m["yes_price_dollars"])
                        n = float(m.get("count_fp") or 0)
                    except (KeyError, TypeError, ValueError):
                        continue
                    tau = close - ts
                    if not (0 <= tau <= 180):
                        continue
                    side = m.get("taker_side")
                    if side not in ("yes", "no"):
                        continue
                    paid = yes_px if side == "yes" else 1.0 - yes_px
                    if not (0.90 <= paid <= 0.98 + 1e-9):
                        continue
                    et_day = dt.datetime.fromtimestamp(ts + ET_OFF, dt.UTC).strftime("%m-%d")
                    res = settled.get(tk)
                    if res is None:
                        agg.unjoined[et_day].add(tk)
                        continue
                    agg.joined[et_day].add(tk)
                    won_yes = (res == "yes")
                    won = (side == "yes" and won_yes) or (side == "no" and not won_yes)
                    agg.trades_seen += 1
                    agg.add(ser, tau, paid, bool(won), n, close, tk, ts)
        except EOFError:
            truncated += 1   # hour still being written / cut mid-member; rows before the tear KEPT
        except Exception as e:                                  # noqa: BLE001
            torn += 1
            print("    torn: %s (%s)" % (os.path.basename(f), e), flush=True)
        if not i % 24:
            print("    %d/%d hours, %d joined trades, %.0fs" % (i, len(files), agg.trades_seen, time.time() - t0), flush=True)
    return torn, truncated


def fmt_cells(d, title):
    out = ["", "  " + title,
           "  %-8s %-8s | %6s %6s %6s %9s | %6s %6s %6s %6s %7s %7s %5s %s" % (
               "tau s", "price", "wClos", "wMkts", "wTrd", "wContr",
               "aClos", "aMkts", "lostC", "lostM", "lossC%", "lossM%", "BE%", "flag")]
    for (tb, pb) in [(t, p) for t in TAU_BANDS for p in PX_BANDS]:
        c = d.get((tb, pb))
        if not c or not c["a_trades"]:
            out.append("  %-8s %-8s | %6s" % ("%d-%d" % tb, "%.0f-%.0f" % (pb[0]*100, pb[1]*100), "-"))
            continue
        nc = len(c["a_closes"]); nm = len(c["a_mkts"])
        lc = len(c["a_lost_closes"]); lm = len(c["a_lost_mkts"])
        lossc = 100.0 * lc / nc; lossm = 100.0 * lm / nm
        pmean = c["a_paid_x_n"] / c["a_trades"]
        be = break_even(pmean)
        flag = ("clears(C)" if lossc < be else "FAILS(C)") + ("/clears(M)" if lossm < be else "/FAILS(M)")
        if nc < 30:
            flag += " n<30"
        out.append("  %-8s %-8s | %6d %6d %6d %9.0f | %6d %6d %6d %6d %6.2f%% %6.2f%% %5.2f %s" % (
            "%d-%d" % tb, "%.0f-%.0f" % (pb[0]*100, pb[1]*100),
            len(c["w_closes"]), len(c["w_mkts"]), c["w_trades"], c["w_contracts"],
            nc, nm, lc, lm, lossc, lossm, be, flag))
    return "\n".join(out)


def fmt_tau_totals(d, title):
    """Collapse price bands: per tau band, winning-side supply and all-taker loss."""
    out = ["", "  " + title,
           "  %-8s | %6s %6s %9s | %6s %6s %7s %7s" % ("tau s", "wClos", "wMkts", "wContr", "aClos", "lostC", "lossC%", "lossM%")]
    for tb in TAU_BANDS:
        wc, wm, wn, ac, am, lc, lm = set(), set(), 0.0, set(), set(), set(), set()
        for pb in PX_BANDS:
            c = d.get((tb, pb))
            if not c:
                continue
            wc |= c["w_closes"]; wm |= c["w_mkts"]; wn += c["w_contracts"]
            ac |= c["a_closes"]; am |= c["a_mkts"]; lc |= c["a_lost_closes"]; lm |= c["a_lost_mkts"]
        if not ac:
            out.append("  %-8s | -" % ("%d-%d" % tb)); continue
        out.append("  %-8s | %6d %6d %9.0f | %6d %6d %6.2f%% %6.2f%%" % (
            "%d-%d" % tb, len(wc), len(wm), wn, len(ac), len(lc),
            100.0 * len(lc) / len(ac), 100.0 * len(lm) / len(am)))
    return "\n".join(out)


def fmt_days(agg):
    out = ["", "  PER ET DAY: contracts of WINNING-side taker buys at 90-98c (pooled 9 series; BTC in brackets)",
           "  %-6s | %9s %9s %9s | %6s | %7s %7s %7s | %7s %7s" % (
               "ET day", "0-30s", "31-60s", "61-120s", "0-30 %", "cl0-30", "cl31-60", "cl61-120", "joined", "unjoin")]
    for day in sorted(set(agg.day) | set(agg.unjoined) | set(agg.joined)):
        d = agg.day[day]
        a, b, c = d["0-30"], d["31-60"], d["61-120"]
        tot = a + b + c
        share = 100.0 * a / tot if tot else 0.0
        out.append("  %-6s | %5.0f[%4.0f] %5.0f[%4.0f] %5.0f[%4.0f] | %5.1f%% | %7d %7d %7d | %7d %7d" % (
            day, a, d["btc 0-30"], b, d["btc 31-60"], c, d["btc 61-120"], share,
            len(agg.day_closes[day]["0-30"]), len(agg.day_closes[day]["31-60"]),
            len(agg.day_closes[day]["61-120"]),
            len(agg.joined[day]), len(agg.unjoined[day])))
    return "\n".join(out)


def run(lo, hi, label):
    files = sorted(f for f in glob.glob(os.path.join(DATA, "*.jsonl.gz"))
                   if lo <= os.path.basename(f)[:11] <= hi)
    print("== %s: %d tape hours (%s .. %s)" % (label, len(files),
          os.path.basename(files[0]) if files else "-", os.path.basename(files[-1]) if files else "-"), flush=True)
    settled = load_outcomes()
    print("  settlements on file: %d" % len(settled), flush=True)
    agg = Agg()
    torn, truncated = walk(files, settled, agg)
    print("  joined trades at 90-98c within 180 s: %d; torn hours skipped: %d; truncated hours (rows before tear kept): %d"
          % (agg.trades_seen, torn, truncated))
    print(fmt_cells(agg.cells, "TABLE 1+2 POOLED 9 SERIES (%s). w*=winning-side taker buys; a*=all takers; C=quarter-hour closes, M=markets; BE at mean paid" % label))
    print(fmt_tau_totals(agg.cells, "POOLED, price bands collapsed (90-98c)"))
    print(fmt_cells(agg.btc, "TABLE 1+2 BTC ALONE (%s)" % label))
    print(fmt_tau_totals(agg.btc, "BTC, price bands collapsed (90-98c)"))
    print(fmt_days(agg))
    print()


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "recent"
    if which == "recent":
        run("20260912T00", "20260918T23", "LAST 6 DAYS 09-12..09-18 UTC files")
    else:
        run("20260906T00", "20260911T23", "PRIOR 6 DAYS 09-06..09-11 UTC files")
