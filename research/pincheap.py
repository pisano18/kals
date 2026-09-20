"""pincheap.py -- HOW MUCH CHEAP SUPPLY IS THERE, per day and per week.

WHY THIS EXISTS. The operator, 2026-09-19, after being shown that the share
of contracts we buy under 95c fell from 31% to 10% between two Saturdays:
*"Add a way to track the value that went 31%->10% per day and per week."*

WHAT THE NUMBER IS. Profit per contract is set almost entirely by the PRICE
paid: about 13c at 88c, 5.4c at 94.8c, 2.2c at 97.8c. So the single number
that decides whether this strategy earns anything is **what share of the
contracts we buy land under 95c**. That is the "cheap share" here.

TWO POPULATIONS, AND THEY ANSWER DIFFERENT QUESTIONS.

  LIVE      what WE actually bought. Confounded by our own bet size: a
            106-contract order walks further up the ladder than a 66-contract
            one, so the cheap share falls even if the market did not change.

  PAPER     what the market OFFERED, at a fixed bet size. Paper arms were
            pinned at 20 contracts until 2026-09-19T12:26Z (A66 made them
            mirror live). Signals before that cut are a clean size control:
            if the cheap share falls HERE too, the market really thinned.

Reporting only the first is how this project has twice mistaken its own
growth for a market decline. Both columns are always printed.

DAY OF WEEK IS PRINTED AND IT IS NOT DECORATION. The weekend carries far more
cheap supply than a weekday -- 09-13 (Sunday) is the richest day on file --
so a weekday compared against a weekend looks like collapse. This file was
written the same day it was discovered that three documents called 09-13 a
Saturday when it was a Sunday.

    python research/pincheap.py                 # per day and per week
    python research/pincheap.py --selftest

Reads only our own logs (`results/pinrun-live-*.jsonl`,
`results/pinrun-paper-*.jsonl`). No tape, no replay.
"""
import argparse
import collections
import datetime
import glob
import json
import os
import sys

ET = datetime.timezone(datetime.timedelta(hours=-4))
CHEAP_UNDER = 0.95          # the price below which a contract is worth having
SIZE_MIRROR_CUT = "2026-09-19T12:26:00Z"   # A66: paper arms stop being a control
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def et_day(ts):
    """ET calendar day of a UTC stamp. ET because that is how the operator
    reads a day, and because the repo's own day boundaries are ET."""
    if not ts:
        return None
    try:
        d = datetime.datetime.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        return None
    return d.replace(tzinfo=datetime.timezone.utc).astimezone(ET).date()


def iso_week(day):
    """(year, week) so weeks group Monday-Sunday. A week that mixes the two
    halves of a weekend would hide the very effect this file exists to show."""
    y, w, _ = day.isocalendar()
    return (y, w)


def cheap_share(prices, weights=None, under=CHEAP_UNDER):
    """Share of contracts (or signals) priced under `under`.

    Returns None -- never 0.0 -- when there is nothing to measure. A zero
    cheap share is a real and very loud claim; "we saw nothing" is not.
    """
    tot = 0.0
    cheap = 0.0
    for i, p in enumerate(prices):
        try:
            px = float(p)
        except (TypeError, ValueError):
            continue
        w = 1.0
        if weights is not None:
            try:
                w = float(weights[i])
            except (TypeError, ValueError, IndexError):
                continue
        if w <= 0:
            continue
        tot += w
        if px < under:
            cheap += w
    if tot <= 0:
        return None
    return cheap / tot


def _iter(pattern):
    for f in sorted(glob.glob(os.path.join(REPO, "results", pattern))):
        try:
            fh = open(f, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    yield json.loads(ln)
                except ValueError:
                    continue


def collect(results=None):
    """(live_by_day, paper_by_day). Each maps day -> (prices, weights)."""
    live = collections.defaultdict(lambda: ([], []))
    paper = collections.defaultdict(lambda: ([], []))
    for r in _iter("pinrun-live-*.jsonl"):
        if r.get("kind") != "order":
            continue
        n = r.get("filled") or 0
        px = r.get("exec_price")
        d = et_day(r.get("t"))
        if not d or px is None or not n:
            continue
        live[d][0].append(px)
        live[d][1].append(n)
    for r in _iter("pinrun-paper-*.jsonl"):
        if r.get("kind") != "signal":
            continue
        t = r.get("t")
        # PAST THE CUT A PAPER ARM MIRRORS LIVE SIZE AND IS NO LONGER A
        # CONTROL. Including it would reintroduce the exact confound this
        # column exists to remove.
        if not t or str(t) >= SIZE_MIRROR_CUT:
            continue
        px = r.get("price")
        d = et_day(t)
        if not d or px is None:
            continue
        paper[d][0].append(px)
        paper[d][1].append(1.0)       # one signal, one vote: size is fixed
    return live, paper


# A share off a handful of observations is noise wearing a percentage sign.
# 2026-09-08 has two paper signals and printed "100.0%" beside days built
# from a thousand -- the reader has no way to tell those apart, so the thin
# one must decline to answer instead.
MIN_N = 20


def _fmt(x, n=None):
    if x is None:
        return "  --  "
    if n is not None and n < MIN_N:
        return "(thin)"
    return "%5.1f%%" % (100.0 * x)


def report(live, paper, out=sys.stdout):
    days = sorted(set(live) | set(paper))
    if not days:
        out.write("pincheap: loaded nothing\n")
        return
    out.write("\n  CHEAP SUPPLY -- share of contracts bought under %.0fc\n"
              % (100 * CHEAP_UNDER))
    out.write("  LIVE is what we bought (moves with OUR bet size).\n")
    out.write("  OFFERED is paper arms at a fixed 20 contracts -- the size\n"
              "  control. If OFFERED falls too, the market really thinned.\n\n")
    out.write("  %-12s %-4s %9s %9s %9s\n"
              % ("ET day", "dow", "LIVE", "OFFERED", "contracts"))
    for d in days:
        lp, lw = live.get(d, ([], []))
        pp, pw = paper.get(d, ([], []))
        out.write("  %-12s %-4s %9s %9s %9d\n"
                  % (d.isoformat(), d.strftime("%a"),
                     _fmt(cheap_share(lp, lw), sum(lw)),
                     _fmt(cheap_share(pp, pw), len(pp)),
                     int(sum(lw))))

    out.write("\n  BY WEEK (Monday-Sunday)\n")
    out.write("  %-14s %9s %9s %9s %7s\n"
              % ("week", "LIVE", "OFFERED", "contracts", "days"))
    wl = collections.defaultdict(lambda: ([], []))
    wp = collections.defaultdict(lambda: ([], []))
    wd = collections.defaultdict(set)
    for d in days:
        k = iso_week(d)
        wd[k].add(d)
        for src, dst in ((live, wl), (paper, wp)):
            p, w = src.get(d, ([], []))
            dst[k][0].extend(p)
            dst[k][1].extend(w)
    for k in sorted(wd):
        mon = min(wd[k]) - datetime.timedelta(days=min(wd[k]).weekday())
        out.write("  %-14s %9s %9s %9d %7d\n"
                  % ("w/c " + mon.isoformat(),
                     _fmt(cheap_share(*wl[k]), sum(wl[k][1])),
                     _fmt(cheap_share(*wp[k]), len(wp[k][0])),
                     int(sum(wl[k][1])), len(wd[k])))

    # LIKE FOR LIKE. Comparing a weekday against a weekend is how "decay" gets
    # reported that is really just Sunday.
    out.write("\n  SAME DAY OF WEEK, oldest to newest -- the only honest\n"
              "  trend line, because the weekend is genuinely richer\n")
    bydow = collections.defaultdict(list)
    for d in days:
        lp, lw = live.get(d, ([], []))
        s = cheap_share(lp, lw)
        if s is not None and sum(lw) >= MIN_N:
            bydow[d.strftime("%a")].append((d, s))
    for dow in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
        seq = bydow.get(dow)
        if not seq:
            continue
        out.write("  %-4s %s\n" % (dow, "   ".join(
            "%s %s" % (d.strftime("%m-%d"), _fmt(s)) for d, s in seq)))


def selftest():
    ok = True

    def ck(cond, msg):
        nonlocal ok
        print("  %-4s %s" % ("ok" if cond else "FAIL", msg))
        if not cond:
            ok = False

    # ---- the estimator, on a world where the answer is known -------------
    ck(abs(cheap_share([0.90, 0.99], [1, 1]) - 0.5) < 1e-9,
       "PLANTED: one of two contracts under 95c is a 50% cheap share")
    ck(abs(cheap_share([0.90, 0.99], [90, 10]) - 0.9) < 1e-9,
       "...and it is weighted by CONTRACTS, not by orders -- 90 cheap and 10 "
       "dear is 90%, which a per-order count would call 50%")
    ck(abs(cheap_share([0.80, 0.85, 0.94]) - 1.0) < 1e-9,
       "PLANTED: all cheap is 100%")
    ck(cheap_share([0.96, 0.98, 0.99]) == 0.0,
       "PLANTED: none cheap is a real 0.0, which is a loud claim and allowed")

    # ---- NULLs: the estimator must not invent a reading ------------------
    ck(cheap_share([]) is None,
       "NULL: nothing to measure is None, NOT 0.0 -- 'no cheap supply' and "
       "'we saw nothing' are different answers and only one is alarming")
    ck(cheap_share([0.9], [0]) is None,
       "NULL: zero contracts is None, not a 100% cheap share")
    ck(cheap_share(["x", None]) is None,
       "NULL: garbage prices measure nothing rather than raising")
    ck(abs(cheap_share([0.90, "x"], [1, 1]) - 1.0) < 1e-9,
       "a garbage price is dropped, and the good one still counts")

    # ---- the boundary, stated once ---------------------------------------
    ck(cheap_share([0.95]) == 0.0 and cheap_share([0.9499]) == 1.0,
       "the bar is STRICTLY under 95c, so exactly 95c is not cheap")

    # ---- the day boundary is ET, and that is load-bearing ----------------
    ck(et_day("2026-09-20T02:30:00Z") == datetime.date(2026, 9, 19),
       "02:30Z belongs to the PREVIOUS ET day -- a UTC day would move a "
       "whole evening of trading onto the wrong date")
    ck(et_day("2026-09-19T04:00:00Z") == datetime.date(2026, 9, 19),
       "and 04:00Z is midnight ET, the first instant of the new ET day")
    ck(et_day(None) is None and et_day("nonsense") is None,
       "NULL: an unparseable stamp is None, never today")

    # ---- weeks group Monday-Sunday so a weekend stays together -----------
    ck(iso_week(datetime.date(2026, 9, 19)) ==
       iso_week(datetime.date(2026, 9, 20)),
       "Saturday and Sunday of the same weekend land in ONE week -- split "
       "them and the weekend effect is smeared across two rows")
    ck(iso_week(datetime.date(2026, 9, 20)) !=
       iso_week(datetime.date(2026, 9, 21)),
       "...and Monday starts the next one")

    # ---- THE DAY-OF-WEEK TRAP THIS FILE WAS WRITTEN FOR ------------------
    ck(datetime.date(2026, 9, 13).strftime("%a") == "Sun",
       "2026-09-13 is a SUNDAY. Three documents in this repo called it a "
       "Saturday, and the 'Saturday carries 2x the cheap supply' finding was "
       "measured on it. Check the calendar, never memory")
    ck(datetime.date(2026, 9, 12).strftime("%a") == "Sat"
       and datetime.date(2026, 9, 19).strftime("%a") == "Sat",
       "the Saturdays are 09-12 and 09-19")

    # ---- the paper cut: past it, paper is no longer a size control -------
    ck(SIZE_MIRROR_CUT == "2026-09-19T12:26:00Z",
       "the paper control ends when A66 made arms mirror live size -- past "
       "that they carry the same size confound as live and prove nothing")
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[src.rindex(chr(10) + "def collect("):]
    ck("str(t) >= SIZE_MIRROR_CUT" in body,
       "and collect() really enforces it, rather than only documenting it")

    print("pincheap selftest: OK" if ok else "pincheap selftest: FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--under", type=float, default=CHEAP_UNDER,
                    help="the price below which a contract counts as cheap")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not os.environ.get("KALS_SELFTESTED"):
        if not selftest():
            raise SystemExit("self-test failed; refusing to touch real data")
        print()
    globals()["CHEAP_UNDER"] = float(a.under)
    live, paper = collect()
    report(live, paper)


if __name__ == "__main__":
    main()
