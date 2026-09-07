#!/usr/bin/env python3
# VERSION: 2026-09-07-r1
"""runreview.py -- read a goldquote run log and say what actually happened.

THE OPERATOR'S REQUIREMENT, verbatim: "if something goes wrong, we will have so
much set up to analyze why and come back stronger" and "make sure you record
their reaction".

So this answers, from the JSONL the run wrote:

  1. WHAT WE DID     every order, amend, stand-down, and why.
  2. WHAT THE BOOK DID AROUND US -- the competitor score before we arrived and
     after, per window. This is the competitor-reaction measurement: if the
     denominator grows once we start quoting, somebody responded.
  3. WHAT WE EARNED  our modelled share per second, integrated over the window,
     and the rebate that implies -- to be checked against the credit that
     lands 48 h later.
  4. WHAT IT COST    fills, inventory, realised P&L.
  5. HOW IT COMPARES to the pre-registered prediction.

Read-only. Takes the newest run log unless given a path.
"""
import collections
import glob
import io
import json
import os
import statistics
import sys

RESULTS = r"C:\kals-repo\results"
POOL, FLOOR = 20.0, 1.00


def load(path):
    out = []
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        cands = sorted(glob.glob(os.path.join(RESULTS, "run-live-*.jsonl")),
                       key=os.path.getmtime)
        if not cands:
            raise SystemExit("no live run log found")
        path = cands[-1]
    ev = load(path)
    print(f"  {os.path.basename(path)}   {len(ev)} events\n")
    if not ev:
        raise SystemExit("empty log")

    start = next((e for e in ev if e.get("kind") == "start"), {})
    end = next((e for e in ev if e.get("kind") == "end"), None)
    print(f"  size {start.get('size')}/side   series {start.get('series')}   "
          f"cap ${start.get('cap')}   abort ${start.get('abort')}")
    print(f"  started {start.get('t')}  balance ${start.get('balance')}")

    kinds = collections.Counter(e.get("kind") for e in ev)
    print(f"\n  EVENT COUNTS: {dict(kinds)}")

    # ---- 1. what we did --------------------------------------------------
    placed = [e for e in ev if e.get("kind") == "place"]
    amended = [e for e in ev if e.get("kind") == "amend"]
    rejected = [e for e in ev if e.get("kind") == "place_rejected"]
    stood = collections.Counter(e.get("why") for e in ev
                                if e.get("kind") == "stand_down")
    print(f"\n  1. WHAT WE DID")
    print(f"     orders placed  {len(placed)}   amended {len(amended)}   "
          f"rejected {len(rejected)}")
    if stood:
        print(f"     stood down     {dict(stood)}")
    for e in rejected[:5]:
        print(f"       REJECTED {e.get('side')} @ {e.get('price')} -> "
              f"{e.get('status')} {str(e.get('response'))[:110]}")

    # ---- 2. competitor reaction -----------------------------------------
    print(f"\n  2. DID THE BOOK REACT TO US?")
    books = [e for e in ev if e.get("kind") == "book"]
    if not books:
        print("     no book observations recorded")
    else:
        # our first order marks the moment we became visible
        first = placed[0]["t"] if placed else None
        before = [b for b in books if first and b["t"] < first]
        after = [b for b in books if first and b["t"] >= first]

        def denom(b, side):
            top = b.get("top_yes" if side == "yes" else "top_no") or []
            return sum(float(s) for _, s in top)
        for side in ("yes", "no"):
            bb = [denom(b, side) for b in before if b.get("top_" + side)]
            aa = [denom(b, side) for b in after if b.get("top_" + side)]
            if len(bb) >= 3 and len(aa) >= 3:
                mb, ma = statistics.median(bb), statistics.median(aa)
                print(f"     {side}: top-3 size before we quoted "
                      f"{mb:>8.0f} (n={len(bb)})  after {ma:>8.0f} "
                      f"(n={len(aa)})  ratio {ma/max(mb,1):.2f}x")
            else:
                print(f"     {side}: too few observations either side "
                      f"({len(bb)} before, {len(aa)} after)")
        print(f"     NOTE: our own 20 lots are INSIDE the 'after' figure, so a")
        print(f"     ratio near 1 + our size is NO reaction. Subtract 20 before")
        print(f"     concluding anyone responded.")

    # ---- 3. what we should have earned ----------------------------------
    print(f"\n  3. MODELLED REBATE (to be checked against the real credit)")
    per_window = collections.defaultdict(list)
    win = 0
    for e in ev:
        if e.get("kind") == "window_open":
            win = e.get("n")
        elif e.get("kind") == "book" and win:
            ry, rn = e.get("ref_yes"), e.get("ref_no")
            if ry is None or rn is None:
                per_window[win].append(0.0)
            else:
                ty = sum(float(s) for _, s in (e.get("top_yes") or []))
                tn = sum(float(s) for _, s in (e.get("top_no") or []))
                S = float(start.get("size") or 20)
                per_window[win].append(
                    0.5 * (S / max(ty, S) + S / max(tn, S)))
    tot = 0.0
    for w in sorted(per_window):
        v = per_window[w]
        if not v:
            continue
        share = sum(v) / len(v)
        gross = POOL * share
        paid = gross if gross >= FLOOR else 0.0
        tot += paid
        print(f"     window {w}: mean share {100*share:>5.2f}%  gross "
              f"${gross:>5.2f}  -> paid ${paid:>5.2f}"
              f"{'   (UNDER THE $1 FLOOR)' if paid == 0 else ''}")
    print(f"     MODELLED TOTAL CREDIT: ${tot:.2f}")
    print(f"     (this is our OWN model. The real number appears in the")
    print(f"      balance 48h+ later; the gap between them IS the finding.)")

    # ---- 4. cost ---------------------------------------------------------
    print(f"\n  4. WHAT IT COST")
    pnl = [e for e in ev if e.get("kind") == "pnl"]
    if pnl:
        vals = [e.get("pnl", 0) for e in pnl]
        print(f"     P&L checks {len(pnl)}  last ${vals[-1]:+.2f}  "
              f"worst ${min(vals):+.2f}  best ${max(vals):+.2f}")
        pos = [e for e in pnl if e.get("positions")]
        print(f"     checks with an open position: {len(pos)}/{len(pnl)}")
    if end:
        print(f"     balance ${end.get('start_balance')} -> "
              f"${end.get('end_balance')}  delta ${end.get('delta'):+.4f}")
        if end.get("aborted"):
            print(f"     ABORTED: {end.get('aborted')}")
        print(f"     windows completed: {end.get('windows')}")
    else:
        print(f"     RUN STILL IN PROGRESS (no end event yet)")

    # ---- 5. against the prediction ---------------------------------------
    print(f"\n  5. AGAINST PREREG_2_natgas.md")
    print(f"     predicted credit  $2.00 - $4.72 over 4 windows")
    print(f"     predicted windows clearing the floor: 2 to 4 of 4")
    cleared = sum(1 for w in per_window
                  if per_window[w] and POOL * (sum(per_window[w]) /
                                               len(per_window[w])) >= FLOOR)
    print(f"     modelled here: ${tot:.2f}, {cleared} window(s) cleared")
    print(f"     REAL credit: unknown until ~48h after the last window.")


if __name__ == "__main__":
    main()
