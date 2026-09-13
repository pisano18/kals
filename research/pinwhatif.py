#!/usr/bin/env python3
# VERSION: 2026-09-13-wi1
"""pinwhatif.py -- the live bot against a what-if running beside it.

THE OPERATOR, 2026-09-13, after AMENDMENTS 20/20b/21 were reverted: "whatever
your changes are, keep it running in the background to see what would've
happened if your version that you want to run was live. Because now I've lost
half a days potential. So run it, but not with the buy button live. You run it
as a 'what-if' tracker."

THE RULE THIS INSTALLS, and it should have existed before today: a change to
what trades gets a WHAT-IF RUN FIRST. Not a replay, not an index population --
the real code, on the real feed, at the same moments, with the buy button off.

HOW THE BUY BUTTON IS OFF. `pinrun` without `--live` is `tag = "paper"`. There
is exactly one call to `pintake.take()` in the trade loop and it sits inside
`if live:`. The paper run also writes to `pinrun-paper-*.jsonl`, a different
filename from `pinrun-live-*.jsonl`, so it cannot contaminate any tool that
reads the live record -- every one of them globs `pinrun-live-*`.

WHAT THIS COMPARISON IS GOOD FOR, and what it is not:

  GOOD: SIGNAL RATE. How often each configuration wants to trade, on the same
        feed, at the same moments. That is the number the operator lost half a
        day to, it is measured directly, and it needs no assumption at all.

  NOT:  P&L. The paper run ASSUMES IT GETS THE FILL. Live loses about 28% of
        races (less with the sweep). So the what-if's dollars are optimistic by
        an unknown amount and are printed with that said, not quietly.

  NOT:  SIZE. Auto-sizing only runs live, so the paper run holds whatever
        --size it was started with while the live bot's size follows the bank.
        Contracts are reported so dollars can be read per contract.

THE TWO RUNS DO NOT TAKE THE SAME TRADES, and that is the interesting part. At
the 19:15Z close on 2026-09-13 the live bot bought ETH at 98.00c with 22
seconds left; the what-if, whose wider ruler left it less certain about ETH,
kept scanning and bought HYPE at 97.80c with 8 seconds left. Both won. A
configuration change is not a filter on one stream of trades -- it redirects
which market gets taken, so "did it catch that one" has three answers and not
two: yes, no, or it took a different one.
"""
import argparse
import glob
import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")


def read_run(path):
    """Everything one run did, as counts and lists."""
    out = {"start": None, "signals": [], "fills": [], "settled": [],
           "alarms": [], "first": None, "last": None, "path": path}
    filled = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        k = d.get("kind")
        t = d.get("t")
        if t:
            out["first"] = t if out["first"] is None else min(out["first"], t)
            out["last"] = t if out["last"] is None else max(out["last"], t)
        if k == "start":
            out["start"] = d
        elif k == "signal":
            out["signals"].append(d)
        elif k == "hedge_alarm":
            out.setdefault("alarms", []).append(d)
        elif k == "order" and (d.get("filled") or 0) > 0:
            out["fills"].append(d)
            filled[d.get("ticker")] = float(d.get("filled") or 0)
        elif k == "settled":
            d = dict(d)
            d["_n"] = filled.get(d.get("ticker"))
            out["settled"].append(d)
    # paper mode books a position without an `order` record, so count those too
    if out["start"] and out["start"].get("mode") == "paper" and not out["fills"]:
        out["fills"] = [{"ticker": s.get("ticker"),
                         "filled": s.get("take_n") or s.get("size")}
                        for s in out["signals"]]
        for f in out["fills"]:
            filled[f["ticker"]] = float(f["filled"] or 0)
        for s in out["settled"]:
            if s.get("_n") is None:
                s["_n"] = filled.get(s.get("ticker"))
    return out


def latest(pattern):
    fs = sorted(glob.glob(os.path.join(RESULTS, pattern)),
                key=os.path.getmtime)
    return fs[-1] if fs else None


def hours(run):
    if not run["first"] or not run["last"]:
        return 0.0
    import calendar
    import datetime

    def ts(x):
        return calendar.timegm(datetime.datetime.strptime(
            x, "%Y-%m-%dT%H:%M:%SZ").timetuple())
    return max((ts(run["last"]) - ts(run["first"])) / 3600.0, 0.01)


def _hours(lo, hi):
    import calendar
    import datetime

    def ts(x):
        return calendar.timegm(datetime.datetime.strptime(
            x, "%Y-%m-%dT%H:%M:%SZ").timetuple())
    return max((ts(hi) - ts(lo)) / 3600.0, 0.01)


def overlap(a, b):
    """The window both runs were alive for -- the only fair comparison."""
    if not (a["first"] and b["first"]):
        return None, None
    lo = max(a["first"], b["first"])
    hi = min(a["last"], b["last"])
    return (lo, hi) if lo <= hi else (None, None)


def within(items, lo, hi):
    return [d for d in items if lo <= (d.get("t") or "") <= hi]


def describe(run):
    s = run["start"] or {}
    return ("gate %s, ruler %s, sweep %s"
            % (s.get("pin"), s.get("sigma_ruler"), s.get("sweep_enabled")))


def close_key(ticker):
    """The CLOSE is a TIME, not a market. KXBTC15M-26SEP131230-30 -> 26SEP131230.
    Twelve series settle on one second at rho ~0.8 (hard rule 4), so keying on
    series+time counts one event as twelve."""
    parts = str(ticker).split("-")
    return parts[1] if len(parts) >= 2 else str(ticker)


def stats(run, lo, hi):
    """EVERY metric, over the window both runs were alive for.

    The operator: "I want an entire breakdown of exactly how it would've
    performed just like if it was running live so we can compare performances
    on every metric." So this is the whole sheet, not the headline -- and the
    numbers that are NOT comparable are marked rather than omitted, because
    leaving them out is how a reader assumes they were fine.
    """
    sg = within(run["signals"], lo, hi)
    fl = within(run["fills"], lo, hi)
    st = within(run["settled"], lo, hi)
    ent = [d for d in st if (d.get("cost") or 0) >= 0.5]
    hed = [d for d in st if (d.get("cost") or 0) < 0.5]
    alarms = within(run.get("alarms", []), lo, hi)
    hrs = _hours(lo, hi)

    by_close = defaultdict(list)
    for d in ent:
        by_close[close_key(d.get("ticker"))].append(d)
    lost_closes = sum(1 for v in by_close.values()
                      if any((x.get("pnl_c") or 0) < 0 for x in v))
    multi = sum(1 for v in by_close.values() if len(v) > 1)

    ct = sum(float(d.get("filled") or 0) for d in fl)
    swept = sum(1 for d in fl if d.get("swept"))
    net = sum((d.get("pnl_c") or 0) for d in st) / 100.0
    net_ent = sum((d.get("pnl_c") or 0) for d in ent) / 100.0
    net_hed = sum((d.get("pnl_c") or 0) for d in hed) / 100.0
    losses = sum(1 for d in ent if (d.get("pnl_c") or 0) < 0)

    def avg(xs):
        xs = [x for x in xs if x is not None]
        return (sum(xs) / len(xs)) if xs else float("nan")

    per_close = defaultdict(float)
    for d in st:
        per_close[close_key(d.get("ticker"))] += (d.get("pnl_c") or 0) / 100.0
    best = max(per_close.values()) if per_close else float("nan")
    worst = min(per_close.values()) if per_close else float("nan")

    return {
        "hours": hrs,
        "signals": len(sg),
        "signals_hr": len(sg) / hrs if hrs else float("nan"),
        "fills": len(fl),
        "fill_ratio": (100.0 * len(fl) / len(sg)) if sg else float("nan"),
        "swept": swept,
        "contracts": ct,
        "closes": len(by_close),
        "multi_coin_closes": multi,
        "settled": len(ent),
        "losses": losses,
        "loss_rate_fill": (100.0 * losses / len(ent)) if ent else float("nan"),
        "lost_closes": lost_closes,
        "loss_rate_close": (100.0 * lost_closes / len(by_close))
                           if by_close else float("nan"),
        "net": net,
        "net_entries": net_ent,
        "net_hedges": net_hed,
        "per_hour": net / hrs if hrs else float("nan"),
        "per_day": net * 24.0 / hrs if hrs else float("nan"),
        "per_fill": net / len(fl) if fl else float("nan"),
        "c_per_contract": 100.0 * net / ct if ct else float("nan"),
        "entry_price": 100.0 * avg([d.get("cost") for d in ent]),
        "edge_c": avg([d.get("edge_c") for d in sg]),
        "tau": avg([d.get("tau") for d in sg]),
        "hedge_alarms": len(alarms),
        "alarms_per_fill": (len(alarms) / len(fl)) if fl else float("nan"),
        "best_close": best,
        "worst_close": worst,
    }


ROWS = [
    ("hours compared", "hours", "%.2f", ""),
    ("", None, "", ""),
    ("signals", "signals", "%d", "how often it WANTED to trade"),
    ("signals per hour", "signals_hr", "%.2f", "the number the ruler moved"),
    ("fills", "fills", "%d", ""),
    ("fill ratio %", "fill_ratio", "%.1f", "paper assumes 100%, live races"),
    ("swept fills", "swept", "%d", "bought the next level up"),
    ("contracts", "contracts", "%.0f", "SIZE-FREE -- compare this, not $"),
    ("", None, "", ""),
    ("closes touched", "closes", "%d", "a close is a TIME (rule 4)"),
    ("closes with 2+ coins", "multi_coin_closes", "%d", ""),
    ("settled entries", "settled", "%d", ""),
    ("losses", "losses", "%d", ""),
    ("loss rate, per fill %", "loss_rate_fill", "%.2f", ""),
    ("losing closes", "lost_closes", "%d", ""),
    ("loss rate, per close %", "loss_rate_close", "%.2f", "the honest unit"),
    ("", None, "", ""),
    ("net $", "net", "%+.2f", "entries + hedges"),
    ("  of which entries", "net_entries", "%+.2f", ""),
    ("  of which hedges", "net_hedges", "%+.2f", ""),
    ("$ per hour", "per_hour", "%+.2f", "needs 30+ fills to mean anything"),
    ("$ per day at this rate", "per_day", "%+.2f", "same caveat"),
    ("$ per fill", "per_fill", "%+.3f", "moves with SIZE"),
    ("cents per contract", "c_per_contract", "%+.3f", "does NOT move with SIZE"),
    ("", None, "", ""),
    ("mean entry price (c)", "entry_price", "%.2f", "cheaper = bigger margin"),
    ("mean edge at signal (c)", "edge_c", "%+.2f", ""),
    ("mean seconds left", "tau", "%.1f", ""),
    ("", None, "", ""),
    ("hedge alarms", "hedge_alarms", "%d", ""),
    ("alarms per fill", "alarms_per_fill", "%.3f", "bar item 4: must stay <=0.10"),
    ("best close $", "best_close", "%+.2f", ""),
    ("worst close $", "worst_close", "%+.2f", ""),
]


def report(live, papers, say=print):
    """Full side-by-side. `papers` is a list, so several what-ifs compare at
    once against the same live run and the same window."""
    runs = [("LIVE", live)] + [(p.get("label") or "WHAT-IF", p) for p in papers]
    lines = []
    w = lines.append
    w("FULL PERFORMANCE COMPARISON -- live against every what-if")
    w("")
    for lab, r in runs:
        w("  %-22s %s   (%s)"
          % (lab, describe(r), os.path.basename(r["path"])))
    lo, hi = None, None
    for _lab, r in runs:
        if not r["first"]:
            continue
        lo = r["first"] if lo is None else max(lo, r["first"])
        hi = r["last"] if hi is None else min(hi, r["last"])
    if not lo or not hi or lo > hi:
        w("")
        w("  The runs do not overlap in time yet -- nothing to compare.")
        txt = "\n".join(lines)
        if say:
            say(txt)
        return txt
    w("")
    w("  window both were alive: %s .. %s" % (lo, hi))
    w("")
    cols = [stats(r, lo, hi) for _lab, r in runs]
    head = "  %-24s" % "" + "".join("| %14s " % lab for lab, _ in runs) + "|"
    w(head)
    w("  " + "-" * 24 + ("|" + "-" * 16) * len(runs) + "|")
    for label, key, fmt, note in ROWS:
        if key is None:
            w("  " + " " * 24 + ("|" + " " * 16) * len(runs) + "|")
            continue
        cells = ""
        for c in cols:
            v = c.get(key)
            try:
                txt = fmt % v
            except (TypeError, ValueError):
                txt = "-"
            if v != v:                      # NaN
                txt = "-"
            cells += "| %14s " % txt
        w("  %-24s%s| %s" % (label, cells, note))
    w("")
    w("  READ THE CONTRACTS AND THE LOSS RATES. The dollar rows are not a fair")
    w("  comparison: a what-if ASSUMES it gets every fill (live loses about 28%")
    w("  of its races) and auto-sizing runs only live, so a what-if's size is")
    w("  frozen while the live bot's follows the bank.")
    w("")
    w("  And a what-if is not a filter on the live bot's trades -- it takes")
    w("  DIFFERENT markets. At 19:15Z live bought ETH and the ruler what-if")
    w("  bought HYPE at the same close. Both won.")
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt


def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    import tempfile
    tmp = tempfile.mkdtemp(prefix="pinwhatif-")
    try:
        lp = os.path.join(tmp, "pinrun-live-a.jsonl")
        pp = os.path.join(tmp, "pinrun-paper-a.jsonl")
        with open(lp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "start", "mode": "live",
                                 "pin": 0.995, "sigma_ruler": "live",
                                 "sweep_enabled": True,
                                 "t": "2026-09-13T18:00:00Z"}) + "\n")
            fh.write(json.dumps({"kind": "signal", "ticker": "X",
                                 "t": "2026-09-13T18:30:00Z"}) + "\n")
            fh.write(json.dumps({"kind": "order", "ticker": "X",
                                 "filled": 40.0,
                                 "t": "2026-09-13T18:30:01Z"}) + "\n")
            # INSIDE the overlap on purpose. A settlement at 19:00 is outside
            # the window both runs were alive for and is correctly counted as
            # zero -- the first version of this fixture asserted against that
            # correct behaviour by mistake.
            fh.write(json.dumps({"kind": "settled", "ticker": "X",
                                 "cost": 0.96, "pnl_c": 150.0,
                                 "t": "2026-09-13T18:45:00Z"}) + "\n")
        with open(pp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "start", "mode": "paper",
                                 "pin": 0.99, "sigma_ruler": "maxdown",
                                 "sweep_enabled": True,
                                 "t": "2026-09-13T18:10:00Z"}) + "\n")
            for k in range(3):
                fh.write(json.dumps({"kind": "signal", "ticker": "P%d" % k,
                                     "take_n": 46.0,
                                     "t": "2026-09-13T18:%02d:00Z"
                                          % (20 + k)}) + "\n")
            fh.write(json.dumps({"kind": "settled", "ticker": "P0",
                                 "cost": 0.95, "pnl_c": 200.0,
                                 "t": "2026-09-13T18:50:00Z"}) + "\n")
        live = read_run(lp)
        paper = read_run(pp)
        paper["label"] = "WHAT-IF"
        ck(live["start"]["mode"] == "live" and paper["start"]["mode"]
           == "paper", "both runs are identified by their own start record")
        ck(len(paper["fills"]) == 3,
           "a paper run books a position without an `order` record, so its "
           "signals are counted as fills (%d)" % len(paper["fills"]))
        lo, hi = overlap(live, paper)
        ck(lo == "2026-09-13T18:10:00Z",
           "the overlap starts when the LATER run started (%s)" % lo)
        ck(hi == "2026-09-13T18:45:00Z",
           "and ends when the EARLIER one last wrote (%s) -- comparing "
           "outside the overlap would credit one run with hours the other was "
           "not alive for" % hi)
        ck(len(within(live["signals"], lo, hi)) == 1,
           "the live signal at 18:30 is inside the overlap")
        ck(close_key("KXBTC15M-26SEP131230-30") == "26SEP131230",
           "a close is keyed by TIME, so twelve coins at one close are ONE "
           "close and not twelve (hard rule 4)")
        sl = stats(live, lo, hi)
        ck(sl["fills"] == 1 and sl["contracts"] == 40.0,
           "the live sheet counts 1 fill and 40 contracts (%s, %s)"
           % (sl["fills"], sl["contracts"]))
        ck(abs(sl["net"] - 1.50) < 1e-9,
           "and its net is the settled pnl, $%+.2f" % sl["net"])
        ck(abs(sl["c_per_contract"] - 100.0 * 1.50 / 40.0) < 1e-9,
           "cents per contract is net/contracts (%.3f) -- the one money row "
           "that does NOT move when size does" % sl["c_per_contract"])
        ck(sl["loss_rate_close"] == 0.0 and sl["lost_closes"] == 0,
           "no losing closes in the fixture")
        txt = report(live, [paper], say=None)
        for must in ("signals per hour", "cents per contract",
                     "loss rate, per close", "alarms per fill",
                     "worst close"):
            ck(must in txt, "the sheet carries the %r row" % must)
        ck("assumes it gets every fill" in txt.lower(),
           "and says on its face that the dollar rows are not a fair "
           "comparison")
        ck("DIFFERENT markets" in txt,
           "and that a what-if is not a subset of the live trades")
        paper2 = dict(paper)
        paper2["first"] = "2026-09-14T00:00:00Z"
        paper2["last"] = "2026-09-14T01:00:00Z"
        t2 = report(live, [paper2], say=None)
        ck("do not overlap" in t2,
           "and refuses to compare two runs that were never alive together")
    finally:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)
    print("pinwhatif selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--live-log", default=None)
    ap.add_argument("--paper-log", default=None)
    ap.add_argument("--stale-s", type=int, default=900,
                    help="a paper log untouched for this long is a DEAD run "
                         "and is excluded; including one collapses the shared "
                         "window and the sheet prints nothing")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    lp = a.live_log or latest("pinrun-live-*.jsonl")
    if not lp:
        print("pinwhatif: no live log -- nothing to analyse")
        return 0
    if a.paper_log:
        paths = [a.paper_log]
    else:
        # EVERY what-if STILL WRITING, and only those. Two are running, and
        # comparing only the newest is how a comparison quietly goes missing --
        # but a DEAD run's last record is old, so including it collapses the
        # shared window to nothing and the whole sheet prints "do not overlap".
        # That is exactly what happened the first time this ran, with four
        # paper logs present and two processes alive.
        now = time.time()
        paths = [q for q in glob.glob(os.path.join(RESULTS,
                                                   "pinrun-paper-*.jsonl"))
                 if now - os.path.getmtime(q) < a.stale_s]
        paths.sort(key=os.path.getmtime)
        # AND ONE LOG PER CONFIGURATION, the newest. A restart leaves the old
        # run's log behind, still recent enough to pass the staleness test, and
        # its stale last-record collapses the shared window to nothing. Two
        # runs with the same settings are the same experiment; keep the live
        # one. This is why the sheet printed "do not overlap" with three logs
        # present and two processes alive.
        _by_cfg = {}
        for q in paths:
            _r = read_run(q)
            _s = _r.get("start") or {}
            _cfg = (_s.get("pin"), _s.get("sigma_ruler"),
                    _s.get("max_per_market_run"), _s.get("improve_scope"))
            _by_cfg[_cfg] = q
        paths = sorted(_by_cfg.values(), key=os.path.getmtime)
        if not paths:
            print("pinwhatif: no what-if has written in the last %d s -- "
                  "none is running. Start one, or pass --paper-log to read a "
                  "finished run." % a.stale_s)
            return 0
    papers = []
    for pth in paths:
        r = read_run(pth)
        st = r.get("start") or {}
        r["label"] = ("pin %s/%s%s"
                      % (st.get("pin"), st.get("sigma_ruler") or "live",
                         "/x%s" % st.get("max_per_market_run")
                         if (st.get("max_per_market_run") or 1) > 1 else ""))
        papers.append(r)
    if not papers:
        print("pinwhatif: no what-if is running -- nothing to compare")
        return 0
    report(read_run(lp), papers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
