"""READ-ONLY. Part 2 of the pinrun.py:947 stale-now_s probe.

Adds the three things part 1 did not answer:
  * the SIGNED direction of the gate error (does a stale clock ever CREATE a
    trade, or only ever refuse one?)
  * tau_true 1 and 2 -- the markets that only get looked at BECAUSE tau is
    overstated (TAU_MIN = 3)
  * a MEAN-REVERTING index, because spot substitution is worst when spot is a
    bad predictor (the dip-and-recover that caused the only loss in the replay)
No orders, no network, writes nothing.
"""
import sys, math, random, threading
from collections import defaultdict
sys.path.insert(0, r"C:\kals-repo\research")
import pinrun
from engine import N_AVG

PIN = pinrun.PIN
CLOSE = 1000000
SIG = 1.0


class FakeIdx:
    def __init__(self, ticks):
        self.ticks = {"X": ticks}
        self.lock = threading.RLock()
        s = max(ticks)
        self._spot = (s, ticks[s])
    def spot(self, iid):
        return self._spot[0], self._spot[1], 0.1
    partial = pinrun.IndexWS.partial


def run(kind, phi):
    random.seed(11)
    agg = defaultdict(lambda: [0, 0, 0, 0, 0.0])   # n, stale_only, fresh_only,
                                                   # stale_only_wins, dfair
    for _ in range(4000):
        v, x, vals = 0.0, 0.0, {}
        for s in range(CLOSE - N_AVG, CLOSE):
            x = phi * x + random.gauss(0.0, SIG)   # phi<1 => mean reverting
            v = x if phi < 1.0 else v + random.gauss(0.0, SIG)
            vals[s] = v
        settle = sum(vals[s] for s in range(CLOSE - N_AVG, CLOSE)) / N_AVG
        for tau_true in (1, 2, 3, 4, 5, 8, 11, 20, 30):
            now_true = CLOSE - tau_true
            held = {s: vals[s] for s in vals if s <= now_true}
            if not held:
                continue
            idx = FakeIdx(held)
            for D in (1, 2, 5):
                now_stale = now_true - D
                tau_logged = CLOSE - now_stale
                if not (pinrun.TAU_MIN <= tau_logged <= pinrun.TAU_MAX):
                    continue                      # this look never happens
                p = idx.partial("X", CLOSE, now_true)
                if p is None:
                    continue
                lk, r = p
                mu = (lk + r * idx._spot[1]) / N_AVG
                sd0 = SIG * math.sqrt(max(pinrun.var_factor(int(r), [1.0]), 1e-18))
                for z in (-3.5, -2.6, -2.2, -2.05, -1.9, -1.5,
                          1.5, 1.9, 2.05, 2.2, 2.6, 3.5):
                    K = mu - z * sd0
                    ff = pinrun.fair(idx, "X", CLOSE, now_true, K, SIG)
                    fs = pinrun.fair(idx, "X", CLOSE, now_stale, K, SIG)
                    if ff is None or fs is None:
                        continue
                    a = agg[(tau_true, D)]
                    a[0] += 1
                    a[4] += abs(ff - fs)
                    trade_f = ff >= PIN or ff <= 1 - PIN
                    trade_s = fs >= PIN or fs <= 1 - PIN
                    if trade_s and not trade_f:
                        a[1] += 1
                        won = (settle >= K) if fs >= PIN else (settle < K)
                        a[3] += int(won)
                    if trade_f and not trade_s:
                        a[2] += 1
    print(f"\n{kind}  (phi={phi})   TAU_MIN={pinrun.TAU_MIN} TAU_MAX={pinrun.TAU_MAX}")
    print(f"  {'tau_true':>8} {'D':>2} {'logged':>6} {'cells':>8} "
          f"{'STALE-ONLY trades':>18} {'their wins':>11} {'trades LOST':>12} "
          f"{'mean|dfair|':>11}")
    for key in sorted(agg):
        tau_true, D = key
        n, so, fo, sw, df = agg[key]
        print(f"  {tau_true:>8} {D:>2} {tau_true+D:>6} {n:>8} {so:>18} "
              f"{(str(sw)+'/'+str(so)) if so else '-':>11} {fo:>12} "
              f"{df/n:>11.5f}")


run("random walk", 1.0)
run("mean-reverting (OU, phi=0.85)", 0.85)
