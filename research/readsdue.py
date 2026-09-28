#!/usr/bin/env python3
"""readsdue.py -- what must be read and reported to the operator, and when.

results/READS_DUE.json lists every running test, paper arm, live change with a
watch item, and dated job. This prints the ones that are OVERDUE, due within
the next 24 hours, and coming in the next 7 days, in ET, so a session can
report finished tests UNPROMPTED (CLAUDE.md, "Reads due").

    python research/readsdue.py            # the summary
    python research/readsdue.py --all      # every open item
    python research/readsdue.py --selftest
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                    "results", "READS_DUE.json")


def et(dt):
    """UTC -> ET for display: EDT (UTC-4) from the 2nd Sunday of March to the
    1st Sunday of November, EST (UTC-5) otherwise."""
    y = dt.year
    mar = datetime(y, 3, 8, 7, tzinfo=timezone.utc)
    mar += timedelta(days=(6 - mar.weekday()) % 7)
    nov = datetime(y, 11, 1, 6, tzinfo=timezone.utc)
    nov += timedelta(days=(6 - nov.weekday()) % 7)
    off = -4 if mar <= dt < nov else -5
    return (dt + timedelta(hours=off)).strftime("%a %m-%d %I:%M %p ET")


def parse(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def buckets(items, now):
    over, soon, week = [], [], []
    for it in items:
        if it.get("status") != "open":
            continue
        d = parse(it["due"])
        if d <= now:
            over.append((d, it))
        elif d <= now + timedelta(hours=24):
            soon.append((d, it))
        elif d <= now + timedelta(days=7):
            week.append((d, it))
    return sorted(over, key=lambda x: x[0]), sorted(soon, key=lambda x: x[0]), \
        sorted(week, key=lambda x: x[0])


def selftest():
    fails = []
    now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    items = [{"id": "a", "due": "2026-09-28T11:00Z", "status": "open"},
             {"id": "b", "due": "2026-09-29T06:00Z", "status": "open"},
             {"id": "c", "due": "2026-10-03T00:00Z", "status": "open"},
             {"id": "d", "due": "2026-09-20T00:00Z", "status": "read"},
             {"id": "e", "due": "2026-11-01T00:00Z", "status": "open"}]
    o, s, w = buckets(items, now)
    if [x[1]["id"] for x in o] != ["a"]:
        fails.append("overdue bucket wrong: %s" % [x[1]["id"] for x in o])
    if [x[1]["id"] for x in s] != ["b"]:
        fails.append("24-hour bucket wrong")
    if [x[1]["id"] for x in w] != ["c"]:
        fails.append("7-day bucket wrong")
    if buckets([], now) != ([], [], []):
        fails.append("empty list not empty")
    if et(datetime(2026, 9, 28, 4, 0, tzinfo=timezone.utc)) != "Mon 09-28 12:00 AM ET":
        fails.append("EDT conversion wrong: %s" % et(datetime(2026, 9, 28, 4, 0, tzinfo=timezone.utc)))
    if et(datetime(2026, 12, 1, 5, 0, tzinfo=timezone.utc)) != "Tue 12-01 12:00 AM ET":
        fails.append("EST conversion wrong")
    print("readsdue self-test " + ("PASSED" if not fails else "FAILED: " + "; ".join(fails)))
    return not fails


def main():
    if "--selftest" in sys.argv:
        raise SystemExit(0 if selftest() else 1)
    data = json.load(open(PATH, encoding="utf-8"))
    items = data["items"]
    now = datetime.now(timezone.utc)
    if "--all" in sys.argv:
        for it in sorted(items, key=lambda x: x["due"]):
            print("%-7s %-22s %-20s %s" % (it["status"], et(parse(it["due"])), it["id"], it["what"]))
        return
    o, s, w = buckets(items, now)
    def show(title, rows):
        print(title)
        if not rows:
            print("  (none)")
        for d, it in rows:
            print("  - %s  [%s]  %s" % (et(d), it["id"], it["what"]))
            print("      how: %s" % it["how"])
            print("      bar: %s" % it["bar"])
    show("OVERDUE -- report these to the operator now:", o)
    show("DUE IN THE NEXT 24 HOURS:", s)
    print("COMING THIS WEEK:")
    for d, it in w:
        print("  - %s  [%s]  %s" % (et(d), it["id"], it["what"]))
    if not w:
        print("  (none)")


if __name__ == "__main__":
    main()
