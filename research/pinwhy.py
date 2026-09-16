#!/usr/bin/env python3
"""pinwhy.py -- why are opportunities plummeting?

THE OPERATOR, 2026-09-16: "Opportunities spotted is really, really scary...
please figure out why opportunities is plummeting. What does it mean?"

Signals per day have gone 137, 75, 57, 68, 46. That is the one trend in the
business with no innocent explanation yet, and it is not about our size: a
signal is counted before any order, so a bigger bank cannot reduce it.

FOUR CANDIDATES, and they call for opposite responses:

  UPTIME   fewer hours running means fewer chances. Boring, and fixable.
  SCANNING fewer markets watched, or watched for less of each window.
  OUR OWN GATES  we have ADDED gates continuously -- the dump guard, the jump
           gate, the depth ladder, the hedge. Every one of them can only
           SUBTRACT signals. If the fall is our own rules tightening, then it
           is self-inflicted and reversible, and calling it a market problem
           would be exactly backwards.
  THE MARKET  genuinely fewer mispriced moments out there. The only one that
           is really bad news.

They are separable: a refusal is logged with its gate, so a gate that started
eating signals shows up as its own count rising while the others hold. That is
what this counts, per day, per gate, alongside how long the bot was up and how
many markets it was watching.

SOURCE: live logs only.

    python research/pinwhy.py --selftest
    python research/pinwhy.py
"""
import argparse
import collections
import glob
import json
import sys

LIVE = r"C:\kals-repo\results\pinrun-live-*.jsonl"


def day_of(r):
    return str(r.get("t") or "")[:10]


def hours_of(stamps):
    """Span in hours between the first and last record of a day."""
    if len(stamps) < 2:
        return 0.0
    s = sorted(stamps)
    def sec(x):
        try:
            h, m, ss = x[11:19].split(":")
            return int(h) * 3600 + int(m) * 60 + float(ss)
        except (ValueError, IndexError):
            return None
    a, b = sec(s[0]), sec(s[-1])
    if a is None or b is None:
        return 0.0
    return max(0.0, (b - a) / 3600.0)


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    ck(day_of({"t": "2026-09-13T19:04:00Z"}) == "2026-09-13", "the day parses")
    ck(day_of({}) == "", "NULL: a record with no time has no day")
    h = hours_of(["2026-09-13T01:00:00Z", "2026-09-13T04:30:00Z"])
    ck(abs(h - 3.5) < 1e-6, "a three and a half hour span measures 3.5 (%.2f)" % h)
    ck(hours_of(["2026-09-13T01:00:00Z"]) == 0.0,
       "NULL: one record spans no time, rather than a whole day")
    ck(hours_of([]) == 0.0, "NULL: no records span no time")
    print("pinwhy selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    rows = []
    for fp in sorted(glob.glob(LIVE)):
        for line in open(fp, encoding="utf-8", errors="replace"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    if not rows:
        print("loaded nothing")
        return 0

    days = collections.defaultdict(lambda: {"sig": 0, "ref": 0, "watch": 0,
                                            "stamps": [], "gates":
                                            collections.Counter(),
                                            "tickers": set()})
    for r in rows:
        d = day_of(r)
        if not d:
            continue
        v = days[d]
        v["stamps"].append(r["t"])
        k = r.get("kind")
        if k == "signal":
            v["sig"] += 1
        elif k == "refused":
            v["ref"] += 1
            v["gates"][r.get("gate") or "?"] += 1
            if r.get("ticker"):
                v["tickers"].add(r["ticker"])
        elif k == "watch":
            v["watch"] += 1

    print("\nOPPORTUNITIES PER HOUR THE BOT WAS ACTUALLY UP\n")
    print("  %-12s %6s %8s %8s %9s %10s %9s"
          % ("day", "hours", "signals", "per hr", "looks", "looks/hr", "markets"))
    print("  " + "-" * 68)
    for d in sorted(days):
        v = days[d]
        h = hours_of(v["stamps"])
        looks = v["sig"] + v["ref"]
        print("  %-12s %6.1f %8d %8.1f %9d %10.0f %9d"
              % (d, h, v["sig"], v["sig"] / h if h else 0, looks,
                 looks / h if h else 0, len(v["tickers"])))

    print("\nWHICH GATE IS DOING THE REFUSING, as a share of all looks that day\n")
    gates = [g for g, _ in
             collections.Counter(
                 {g: sum(days[d]["gates"][g] for d in days)
                  for d in days for g in days[d]["gates"]}).most_common()]
    top = sorted({g for d in days for g in days[d]["gates"]},
                 key=lambda g: -sum(days[d]["gates"][g] for d in days))[:6]
    print("  %-12s %8s " % ("day", "signals") + " ".join("%12s" % g[:12] for g in top))
    print("  " + "-" * (22 + 13 * len(top)))
    for d in sorted(days):
        v = days[d]
        looks = v["sig"] + v["ref"] or 1
        cells = " ".join("%11.0f%%" % (100 * v["gates"][g] / looks) for g in top)
        print("  %-12s %8.0f%% " % (d, 100 * v["sig"] / looks) + cells)

    print("\n  A gate whose share RISES while signals fall is eating them, and")
    print("  that is our own doing and reversible. If every share holds steady")
    print("  and the LOOKS themselves fall, the bot is seeing less of the")
    print("  market. If looks hold and signals fall with no gate rising, the")
    print("  market really is offering fewer mispriced moments.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
