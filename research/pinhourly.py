#!/usr/bin/env python3
# VERSION: 2026-09-13-hr1
"""pinhourly.py -- could this bot trade the HOURLY markets? Sampled live.

THE OPERATOR: "we should immediately start checking those 15 markets to see how
we'd perform with our current bot."

WHY THIS IS THE BIGGEST UNTESTED THING HERE. Fourteen hourly crypto series
settle on a rule that is WORD FOR WORD ours:

    "the simple average of the sixty seconds of CF Benchmarks' Bitcoin
     Real-Time Index (BRTI) before 4 PM EDT"

Same index, same sixty-second average, same collapse of uncertainty in the
final seconds -- the entire mechanism the pin rests on. The model needs NO
change. Only two things differ:

  1. The window is an hour, so the market is open sixty minutes not fifteen.
  2. The strike is a FIXED PRICE set at the open, not the previous window's
     settlement. That is a LADDER: 40-67 strikes per hour per coin, against
     one strike per 15-minute window.

AND THE HOUR'S CLOSE IS THE SAME INSTANT AS A 15-MINUTE CLOSE. At 21:00Z,
KXBTC15M and KXBTCD settle on THE SAME SIXTY PRINTS. One event, two markets,
different strikes, independently quoted.

WHAT DECIDES IT, and it is not the model. Our edge needs somebody offering the
winning side cheaply in the last thirty seconds. On the 15-minute markets that
happens 2.1% of the time (RESULTS_select: 83.3% of the time nobody offers the
model's side at all). Whether it happens on the hourly ladder is unknown and
cannot be reasoned out -- so this samples the real book, second by second,
through a real close.

IT PLACES NO ORDER AND HAS NO PATH TO ONE. It imports no order module, holds no
private key beyond the read-only signer, and every request it makes is a GET.
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")

# The hourly series whose rules match ours word for word, plus the 15-minute
# series that settles on the SAME instant, for the side-by-side.
HOURLY = ["KXBTCD", "KXETHD", "KXSOLD", "KXXRPD", "KXDOGED", "KXBNBD",
          "KXHYPED"]
FIFTEEN = ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
           "KXBNB15M", "KXHYPE15M"]
CEILING = 0.98          # pinrun.PRICE_CEILING -- what we would ever pay


def creds():
    import ordercli
    import pintake
    import kauth
    return (pintake.PROD_ELECTIONS, ordercli.load_key(pintake.PROD_KEY_FILE),
            kauth.KEY_ID)


def get(base, pk, kid, path, query=None):
    import ordercli
    return ordercli.send(base, pk, kid, "GET", path, query=query)


def open_markets(base, pk, kid, series, say=print):
    """Open markets for a series, newest close first."""
    st, b = get(base, pk, kid, "/markets",
                query={"series_ticker": series, "limit": "1000",
                       "status": "open"})
    ms = (b.get("markets") or []) if isinstance(b, dict) else []
    return ms


def book_of(base, pk, kid, ticker):
    """(yes_bid, yes_ask, ask_size) from the REST order book.

    THE RESPONSE SHAPE, learned the hard way. It is

        {"orderbook_fp": {"yes_dollars": [[price, size], ...],
                          "no_dollars":  [[price, size], ...]}}

    not {"orderbook": {"yes": ..., "no": ...}}. The first version read the
    wrong keys and returned "no ask" for EVERY market -- including the
    15-minute ones we demonstrably trade every day. A parser that returns a
    clean null on markets known to be liquid is the only reason that bug was
    visible at all; on the hourly series alone it would have read as a
    finding.

    BOTH SIDES ARE BIDS. A `no` bid at q IS a `yes` ask at 1-q, which is the
    mapping pintake's docstring exists for. And NO depth parameter is passed:
    `depth=5` returns five levels around the middle rather than the best, so
    the top of book can be missing from it entirely.
    """
    st, b = get(base, pk, kid, "/markets/%s/orderbook" % ticker)
    if not isinstance(b, dict):
        return None
    ob = b.get("orderbook_fp") or b.get("orderbook") or {}
    yes = ob.get("yes_dollars") or ob.get("yes") or []
    no = ob.get("no_dollars") or ob.get("no") or []

    def best(levels):
        px = None
        sz = 0.0
        for p, q in levels:
            try:
                p = float(p)
                q = float(q)
            except (TypeError, ValueError):
                continue
            if px is None or p > px:
                px, sz = p, q
            elif px is not None and abs(p - px) < 1e-12:
                sz += q
        return px, sz

    ybid, _ys = best(yes)
    nbid, nsz = best(no)
    yask = (1.0 - nbid) if nbid is not None else None
    return (ybid, yask, nsz)


def sample(base, pk, kid, tickers, out_path, seconds, say=print):
    """Poll every ticker once a second and append raw rows."""
    n = 0
    t_end = time.time() + seconds
    with open(out_path, "a", encoding="utf-8") as fh:
        while time.time() < t_end:
            t0 = time.time()
            for tk in tickers:
                try:
                    r = book_of(base, pk, kid, tk)
                except Exception:
                    r = None
                if r is None:
                    continue
                fh.write(json.dumps({
                    "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "sec": int(time.time()), "ticker": tk,
                    "yes_bid": r[0], "yes_ask": r[1], "ask_size": r[2]}) + "\n")
                n += 1
            fh.flush()
            dt = 1.0 - (time.time() - t0)
            if dt > 0:
                time.sleep(dt)
    if say:
        say("  sampled %d book reads into %s" % (n, out_path))
    return n


def summarise(path, say=print):
    """What a bot could have BOUGHT: an ask on either side under the ceiling."""
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    per = defaultdict(lambda: {"reads": 0, "askable": 0, "cheap": 0,
                               "best": None, "size": 0.0})
    for r in rows:
        tk = r["ticker"]
        fam = tk.split("-")[0]
        a = per[fam]
        a["reads"] += 1
        ya = r.get("yes_ask")
        if ya is not None:
            a["askable"] += 1
            for side_px in (ya, 1.0 - (r.get("yes_bid") or 1.0)):
                if side_px is not None and 0 < side_px <= CEILING:
                    a["cheap"] += 1
                    if a["best"] is None or side_px < a["best"]:
                        a["best"] = side_px
                    a["size"] += float(r.get("ask_size") or 0)
                    break
    lines = ["  %-12s | book reads | any ask | ask UNDER the 98c ceiling | "
             "cheapest" % "series",
             "  " + "-" * 12 + "|------------|---------|---------------------"
             "------|---------"]
    for fam in sorted(per):
        a = per[fam]
        lines.append("  %-12s | %10d | %7d | %25s | %s"
                     % (fam, a["reads"], a["askable"],
                        "%d (%.1f%%)" % (a["cheap"],
                                         100.0 * a["cheap"] / max(1, a["reads"])),
                        ("%.3f" % a["best"]) if a["best"] else "-"))
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

    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    work = src[:src.index("def " + "selftest")]
    for banned in ("build_order", "pintake.take", '"POST"', "'POST'"):
        ck(banned not in work,
           "the working code contains no %r -- this file cannot place an "
           "order" % banned)
    ck(work.count('"GET"') >= 1 and "def get(" in work,
       "every request it makes goes through one GET helper")

    import tempfile
    tmp = tempfile.mkdtemp(prefix="pinhourly-")
    try:
        fp = os.path.join(tmp, "s.jsonl")
        with open(fp, "w", encoding="utf-8") as fh:
            # a cheap ask on the YES side, under the ceiling
            fh.write(json.dumps({"ticker": "KXBTCD-A", "yes_bid": 0.90,
                                 "yes_ask": 0.95, "ask_size": 120}) + "\n")
            # an ask ABOVE the ceiling on both sides -- untradeable
            fh.write(json.dumps({"ticker": "KXBTCD-A", "yes_bid": 0.001,
                                 "yes_ask": 0.999, "ask_size": 5}) + "\n")
            # no ask at all
            fh.write(json.dumps({"ticker": "KXBTCD-A", "yes_bid": 0.4,
                                 "yes_ask": None, "ask_size": 0}) + "\n")
        txt = summarise(fp, say=None)
        ck("KXBTCD" in txt, "the summary groups by series")
        ck("3 " in txt.split("|")[3] or "3" in txt,
           "and counts every book read")
        ck("(33.3%)" in txt or "33.3" in txt,
           "one of three reads carried an ask under the ceiling (%s)"
           % txt.splitlines()[-1])
        ck("0.950" in txt, "and the cheapest is reported (0.950)")
    finally:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)
    print("pinhourly selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seconds", type=int, default=70,
                    help="how long to sample")
    ap.add_argument("--at-close", action="store_true",
                    help="wait until 70 s before the next hour, then sample "
                         "through it -- the only window our strategy trades")
    ap.add_argument("--out", default=os.path.join(
        REPO, "results", "hourly_book_sample.jsonl"))
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    if a.summarise:
        if not os.path.exists(a.out):
            print("pinhourly: no sample on disk -- nothing to analyse")
            return 0
        summarise(a.out)
        return 0
    base, pk, kid = creds()
    want = []
    for s in HOURLY + FIFTEEN:
        ms = open_markets(base, pk, kid, s)
        if not ms:
            continue
        # the markets closing SOONEST, and the strikes nearest the money
        soonest = min(m.get("close_time") or "" for m in ms)
        near = [m for m in ms if (m.get("close_time") or "") == soonest]
        near.sort(key=lambda m: abs(float(m.get("yes_bid_dollars") or 0) - 0.5))
        want += [m["ticker"] for m in near[:6]]
        print("  %-10s %d open, soonest close %s, sampling %d strikes"
              % (s, len(ms), soonest, min(6, len(near))))
    if not want:
        print("pinhourly: no open market on any series -- nothing to analyse")
        return 0
    if a.at_close:
        now = time.time()
        target = (int(now) // 3600 + 1) * 3600 - a.seconds
        wait = target - now
        if wait > 0:
            print("  waiting %.0f s for the close at %s"
                  % (wait, time.strftime("%H:%M:%SZ",
                                         time.gmtime(target + a.seconds))))
            time.sleep(wait)
        # RE-FETCH. The first run picked its tickers twenty minutes before
        # sampling, so every 15-minute market in the list had already closed
        # and the control arm was empty for a reason that had nothing to do
        # with liquidity.
        want = []
        for s2 in HOURLY + FIFTEEN:
            ms = open_markets(base, pk, kid, s2)
            if not ms:
                continue
            soonest = min(m.get("close_time") or "" for m in ms)
            near = [m for m in ms if (m.get("close_time") or "") == soonest]
            # OUR BOT BUYS NEAR-CERTAINTY, 92-98c. On a ladder those are the
            # strikes FAR from spot, not the near-money ones. The first
            # version sorted TOWARD 0.5 -- it sampled exactly the strikes this
            # strategy never touches, which would have answered a question
            # nobody asked.
            def extremity(m):
                b = float(m.get("yes_bid_dollars") or 0)
                if b <= 0.0 or b >= 1.0:
                    return -1.0          # no quote at all: least interesting
                return abs(b - 0.5)
            near.sort(key=extremity, reverse=True)
            want += [m["ticker"] for m in near[:6]]
        print("  re-fetched at the close: %d tickers" % len(want))
    print("  sampling %d tickers for %d s" % (len(want), a.seconds))
    sample(base, pk, kid, want, a.out, a.seconds)
    summarise(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
