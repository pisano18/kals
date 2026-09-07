#!/usr/bin/env python3
# VERSION: 2026-09-07-ps1
"""pinscore.py -- grade a pinlive paper/live log against actual settlement.

For each `signal` in the log, look up how the market actually settled and
compute the realised P&L of the trade pinlive would have taken (paper) or did
take (live):

  side yes, bought at price p:  win -> +(1.00 - p),  loss -> -p
  side no,  bought at price p:  win -> +(1.00 - p),  loss -> -p

"win" means the side we took matched the settlement. Reports the realised edge
per contract, the flip rate, and how the realised number compares to the fair
value the model asserted at entry -- a realised P&L below the model's own
implied edge means the model was overconfident (pin.py's central caveat).
"""
import json
import sys
import statistics

sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get

_RES = {}


def settled(tk):
    if tk in _RES:
        return _RES[tk]
    try:
        st, b = get("/markets/" + tk)
        m = (b or {}).get("market") or {}
        _RES[tk] = m.get("result") if m.get("status") == "finalized" else None
    except Exception:
        _RES[tk] = None
    return _RES[tk]


def main():
    path = sys.argv[1]
    sigs = []
    for line in open(path, encoding="utf-8"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("kind") == "signal":
            sigs.append(d)
    print(f"  {len(sigs)} signals in {path}\n")

    scored, pending = [], 0
    wins = 0
    pnl = []
    for s in sigs:
        res = settled(s["ticker"])
        if res is None:
            pending += 1
            continue
        won = (res == s["side"])
        p = float(s["price"])
        gain = (1.0 - p) if won else (-p)
        pnl.append(gain)
        wins += int(won)
        scored.append((s, won, gain))

    print(f"  {'ticker':<30}{'side':>5}{'fair':>7}{'price':>7}{'result':>8}"
          f"{'P&L':>9}")
    print("  " + "-" * 70)
    for s, won, gain in scored[:40]:
        print(f"  {s['ticker'][:29]:<30}{s['side']:>5}{s['fair']:>7.3f}"
              f"{s['price']:>7.2f}{('WIN' if won else 'loss'):>8}"
              f"{100*gain:>8.2f}c")

    if not pnl:
        print(f"\n  none settled yet ({pending} pending). Re-run later.")
        return
    n = len(pnl)
    tot = sum(pnl)
    print(f"\n  SCORED {n} trades ({pending} still pending settlement)")
    print(f"    wins {wins}/{n} = {100*wins/n:.1f}%   flip rate "
          f"{100*(n-wins)/n:.1f}%")
    print(f"    realised P&L per contract: mean {100*tot/n:+.2f}c   "
          f"total {100*tot:+.1f}c over {n} contracts")
    if n >= 2:
        sd = statistics.pstdev(pnl)
        print(f"    sd {100*sd:.1f}c   worst {100*min(pnl):+.1f}c   "
              f"best {100*max(pnl):+.1f}c")
    implied = statistics.mean(
        (s["fair"] - s["price"]) if s["side"] == "yes"
        else ((1 - s["fair"]) - s["price"]) for s, _, _ in scored)
    print(f"    model's own implied edge at entry: {100*implied:+.2f}c/contract")
    print(f"    realised {100*tot/n:+.2f}c vs implied {100*implied:+.2f}c -> "
          f"{'BELOW (model overconfident)' if tot/n < implied - 0.002 else 'consistent'}")


if __name__ == "__main__":
    main()
