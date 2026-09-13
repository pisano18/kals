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
           "first": None, "last": None, "path": path}
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


def report(live, paper, say=print):
    lo, hi = overlap(live, paper)
    lines = []
    w = lines.append
    w("LIVE vs WHAT-IF")
    w("  live   : %s   (%s)" % (describe(live), os.path.basename(live["path"])))
    w("  what-if: %s   (%s)"
      % (describe(paper), os.path.basename(paper["path"])))
    if not lo:
        w("")
        w("  The two runs do not overlap in time yet -- nothing to compare.")
        txt = "\n".join(lines)
        if say:
            say(txt)
        return txt
    import calendar
    import datetime

    def ts(x):
        return calendar.timegm(datetime.datetime.strptime(
            x, "%Y-%m-%dT%H:%M:%SZ").timetuple())
    h = max((ts(hi) - ts(lo)) / 3600.0, 0.01)
    w("  overlap: %s .. %s  (%.2f hours)" % (lo, hi, h))
    w("")
    w("  %-10s | signals | sig/hr | fills | contracts | settled | net $ | "
      "losses" % "")
    w("  -----------|---------|--------|-------|-----------|---------|-------"
      "|-------")
    for lab, run in (("LIVE", live), ("WHAT-IF", paper)):
        sg = within(run["signals"], lo, hi)
        fl = within(run["fills"], lo, hi)
        st = within(run["settled"], lo, hi)
        ent = [d for d in st if (d.get("cost") or 0) >= 0.5]
        ct = sum(float(d.get("filled") or 0) for d in fl)
        w("  %-10s | %7d | %6.2f | %5d | %9.0f | %7d | %+5.2f | %d"
          % (lab, len(sg), len(sg) / h, len(fl), ct, len(st),
             sum((d.get("pnl_c") or 0) for d in st) / 100.0,
             sum(1 for d in ent if (d.get("pnl_c") or 0) < 0)))
    w("")
    sl = len(within(live["signals"], lo, hi))
    sp = len(within(paper["signals"], lo, hi))
    if sl or sp:
        w("  SIGNAL RATE is the number this is FOR, and it needs no "
          "assumptions:")
        w("  the what-if wants to trade %s the live bot does."
          % ("%+.0f%% as often as" % (100.0 * (sp / sl - 1.0)) if sl
             else "-- (live produced none in the overlap)"))
    w("")
    w("  P&L IS NOT A FAIR COMPARISON. The what-if ASSUMES it gets every fill;")
    w("  live loses about 28%% of its races. And auto-sizing runs only live, so")
    w("  the what-if's size is frozen at what it was started with. Read the")
    w("  contracts column, not the dollars.")
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
            fh.write(json.dumps({"kind": "settled", "ticker": "X",
                                 "cost": 0.96, "pnl_c": 150.0,
                                 "t": "2026-09-13T19:00:00Z"}) + "\n")
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
        ck(live["start"]["mode"] == "live" and paper["start"]["mode"]
           == "paper", "both runs are identified by their own start record")
        ck(len(paper["fills"]) == 3,
           "a paper run books a position without an `order` record, so its "
           "signals are counted as fills (%d)" % len(paper["fills"]))
        lo, hi = overlap(live, paper)
        ck(lo == "2026-09-13T18:10:00Z",
           "the overlap starts when the LATER run started (%s)" % lo)
        ck(hi == "2026-09-13T18:50:00Z",
           "and ends when the EARLIER one last wrote (%s) -- comparing "
           "outside the overlap would credit one run with hours the other was "
           "not alive for" % hi)
        ck(len(within(live["signals"], lo, hi)) == 1,
           "the live signal at 18:30 is inside the overlap")
        txt = report(live, paper, say=None)
        ck("P&L IS NOT A FAIR COMPARISON" in txt,
           "the report says on its face that the dollars are not comparable")
        ck("SIGNAL RATE" in txt,
           "and names the number that IS comparable")
        # no overlap at all
        paper2 = dict(paper)
        paper2["first"] = "2026-09-14T00:00:00Z"
        paper2["last"] = "2026-09-14T01:00:00Z"
        t2 = report(live, paper2, say=None)
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
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    lp = a.live_log or latest("pinrun-live-*.jsonl")
    pp = a.paper_log or latest("pinrun-paper-*.jsonl")
    if not lp or not pp:
        print("pinwhatif: need both a live log and a paper log -- nothing to "
              "analyse")
        return 0
    report(read_run(lp), read_run(pp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
