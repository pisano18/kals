#!/usr/bin/env python3
"""sweptwatch.py -- report each NEW swept fill, once.

The operator, 2026-09-13: "Keep a monitor out and tell me the first time we
actually buy something that we would've lost out on before the update."

A swept fill is one where the level we saw was gone and AMENDMENT 18's higher
limit bought the next one instead. Before 2026-09-13 that trade bought nothing.

WHY A FILE AND NOT A SHELL ONE-LINER. The first version kept its
already-reported set in '/c/kals-repo/results/.swept_seen' -- a Git Bash path
handed to WINDOWS python, which cannot read it. os.path.exists returned False
every pass, the set was empty every pass, and the same fill was reported over
and over. The bug was invisible on the happy path: the notification looked
exactly like a correct one.
"""
import glob
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEN = os.path.join(REPO, "results", ".swept_seen")
GLOB = os.path.join(REPO, "results", "pinrun-live-*.jsonl")


def load_seen():
    if not os.path.exists(SEEN):
        return set()
    try:
        with open(SEEN, encoding="utf-8") as fh:
            return {ln.strip() for ln in fh if ln.strip()}
    except OSError:
        return set()


def scan(seen):
    out = []
    for path in sorted(glob.glob(GLOB), key=os.path.getmtime)[-3:]:
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"swept": true' not in line and '"swept":true' not in line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if not d.get("swept") or not (d.get("filled") or 0):
                    continue
                k = d.get("order_id") or d.get("client_order_id")
                if not k or k in seen:
                    continue
                seen.add(k)
                out.append(d)
    return out


def main():
    seen = load_seen()
    # Everything already in the log at start-up is backfill, not news: record
    # it silently so the watch reports only what happens from now on. Without
    # this the first pass replays the whole history as fresh notifications.
    if "--backfill" in sys.argv:
        scan(seen)
        with open(SEEN, "w", encoding="utf-8") as fh:
            fh.write("\n".join(sorted(seen)))
        print("backfilled %d swept fills; watching for new ones" % len(seen))
    while True:
        new = scan(seen)
        for d in new:
            ask = float(d.get("ask_seen") or 0)
            got = float(d.get("exec_price") or 0)
            print("SWEPT FILL %s | asked %.1fc, paid %.1fc (+%.2fc) | "
                  "%g contracts | before today this bought NOTHING"
                  % (d.get("ticker"), 100 * ask, 100 * got,
                     100 * (got - ask), float(d.get("filled") or 0)))
        if new:
            with open(SEEN, "w", encoding="utf-8") as fh:
                fh.write("\n".join(sorted(seen)))
        sys.stdout.flush()
        time.sleep(45)


if __name__ == "__main__":
    main()
