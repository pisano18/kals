"""READ-ONLY probe. Two questions about pinrun.py:947 (now_s captured before
the 11-GET universe pass, then used for tau and fair() in the market loop).

  Q1  How long does the universe pass actually take on this box?  (times the
      same 11 GETs kauth.get makes; no writes, no orders)
  Q2  If now_s is stale by D seconds, how much does fair() move, and can that
      move flip the 0.98 gate -- and if it flips it, does the trade win?

Nothing here places an order or writes outside results/audit/.
"""
import os, sys, time, math, random, json
sys.path.insert(0, r"C:\kals-repo\research")
import pinrun
from engine import N_AVG

MODE = sys.argv[1] if len(sys.argv) > 1 else "both"

# ---------------------------------------------------------------- Q1
if MODE in ("both", "gets"):
    from kauth import get
    series = list(pinrun.SERIES_TO_INDEX)
    print(f"Q1: timing {len(series)} sequential GETs (the universe pass), 3 reps")
    for rep in range(3):
        t0 = time.time()
        per = []
        for s in series:
            a = time.time()
            st, b = get("/markets", {"series_ticker": s, "status": "open",
                                     "limit": "4"})
            per.append((s, st, time.time() - a))
        tot = time.time() - t0
        print(f"  rep{rep}: total {tot:.3f}s  max-single {max(p[2] for p in per):.3f}s"
              f"  statuses {sorted(set(p[1] for p in per))}")
        time.sleep(1.0)

# ---------------------------------------------------------------- Q2
if MODE in ("both", "fair"):
    print("\nQ2: fair() with a stale now_s, synthetic random-walk index")

    class FakeIdx:
        def __init__(self, ticks):
            self.ticks = {"X": ticks}
            import threading
            self.lock = threading.RLock()
            self._spot = max(ticks), ticks[max(ticks)]
        def spot(self, iid):
            s, v = self._spot
            return s, v, 0.1
        partial = pinrun.IndexWS.partial

    random.seed(7)
    rows = []
    SIG = 1.0                      # per-second sd, arbitrary units
    CLOSE = 1000000
    for path in range(4000):
        v = 0.0
        vals = {}
        # prints for the whole window plus a little before
        for s in range(CLOSE - N_AVG, CLOSE):
            v += random.gauss(0.0, SIG)
            vals[s] = v
        settle = sum(vals[s] for s in range(CLOSE - N_AVG, CLOSE)) / N_AVG
        for tau_true in (3, 4, 5, 8, 11, 16, 21, 30):
            now_true = CLOSE - tau_true
            held = {s: vals[s] for s in vals if s <= now_true}
            idx = FakeIdx(held)
            for D in (1, 2, 5):
                now_stale = now_true - D
                # strikes spread around the current conditional mean so the
                # sample lands on both sides of the 0.98 gate
                p = idx.partial("X", CLOSE, now_true)
                if p is None:
                    continue
                lk, r = p
                mu = (lk + r * held[now_true]) / N_AVG
                sd0 = SIG * math.sqrt(pinrun.var_factor(int(r), [1.0])) or 1e-9
                for z in (-3.5, -2.6, -2.2, -2.05, -1.9, 1.9, 2.05, 2.2, 2.6, 3.5):
                    K = mu - z * sd0
                    ff = pinrun.fair(idx, "X", CLOSE, now_true, K, SIG)
                    fs = pinrun.fair(idx, "X", CLOSE, now_stale, K, SIG)
                    if ff is None or fs is None:
                        continue
                    rows.append((tau_true, D, ff, fs, 1 if settle >= K else 0))

    print(f"  {len(rows)} (path, tau, D, strike) cells")
    print(f"  {'tau':>4} {'D':>2} {'|dfair| mean':>13} {'p99':>9} "
          f"{'gate-flips':>10} {'flip win%':>10} {'base win%':>10}")
    from collections import defaultdict
    agg = defaultdict(list)
    for tau, D, ff, fs, w in rows:
        agg[(tau, D)].append((ff, fs, w))
    for (tau, D) in sorted(agg):
        cells = agg[(tau, D)]
        d = sorted(abs(a - b) for a, b, _ in cells)
        # a "gate flip" = the STALE clock says trade and the FRESH clock does not
        flips = [(a, b, w) for a, b, w in cells
                 if ((b >= 0.98 and a < 0.98) or (b <= 0.02 and a > 0.02))]
        wins = [ (w if b >= 0.98 else 1 - w) for a, b, w in flips ]
        base = [ (w if b >= 0.98 else 1 - w) for a, b, w in cells
                 if b >= 0.98 or b <= 0.02 ]
        print(f"  {tau:>4} {D:>2} {sum(d)/len(d):>13.5f} "
              f"{d[int(0.99*len(d))]:>9.5f} {len(flips):>10} "
              f"{(100*sum(wins)/len(wins) if wins else float('nan')):>10.2f} "
              f"{(100*sum(base)/len(base) if base else float('nan')):>10.2f}")
