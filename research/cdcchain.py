#!/usr/bin/env python3
"""cdcchain.py -- does OUR index reproduce THEIR settlement, to the cent?

THE SINGLE MOST VALUABLE TEST AVAILABLE WITHOUT TRADING ACCESS.

On Kalshi, strike(N+1) == settle(N) exactly. That identity is what lets this
project check its own settlement model against 761 real closes. Crypto.com's
binaries carry the same shape -- PERIOD_INDEX counts up, OPEN_TIME of one
window is the CLOSE_TIME of the last -- so if their strikes chain the same way,
every strike they publish is a PUBLISHED SETTLEMENT of the previous window.

That turns a question we cannot otherwise answer:

    their settlement index is not on any public endpoint, so is our CF
    Benchmarks feed close enough to price their contracts?

into one we can answer from tape alone:

    take our feed, compute what we think window N settled at, and compare it
    to the strike they printed for window N+1.

If those agree to a few hundredths of a percent we can price every contract on
that venue today. If they do not, nothing else about this venue matters and the
honest answer is to stop.

WHAT IT DOES NOT ASSUME. That the chain exists at all is the first thing
tested, not taken on faith: if strike(N+1) is unrelated to our settle(N) the
error column says so loudly and the conclusion is "no chain", not "bad feed".
Both the 60-second mean and their documented 60-second trimmed average are
scored, because the two disagree by a few basis points and the tighter fit
identifies which rule is real.

READ-ONLY.

    python research/cdcchain.py --selftest
    python research/cdcchain.py
"""
import argparse
import collections
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import cdcedge                                               # noqa: E402


def trimmed_mean(vals, frac=0.2):
    """CDNA's documented rule: drop the top and bottom `frac` of the prints,
    average the rest. With 60 prints and frac=0.2 that averages the middle 36."""
    if not vals:
        return None
    v = sorted(vals)
    k = int(len(v) * frac)
    core = v[k:len(v) - k] or v
    return sum(core) / len(core)


def window_vals(D, close, n=60):
    return [x for x in (D.get(s) for s in range(close - n, close)) if x is not None]


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    # ten values, 20% trim drops the two lowest and two highest
    v = [1, 2, 3, 4, 5, 6, 7, 8, 9, 1000]
    ck(trimmed_mean(v) == statistics.mean([3, 4, 5, 6, 7, 8]),
       "the trim drops the outlier: %.2f not %.2f"
       % (trimmed_mean(v), statistics.mean(v)))
    ck(abs(trimmed_mean([5.0] * 60) - 5.0) < 1e-12,
       "a flat window trims to the same number")
    ck(trimmed_mean([]) is None,
       "NULL: no prints trims to nothing, never to zero")
    ck(trimmed_mean([1, 2, 3]) == 2.0,
       "and a window too short to trim averages whole rather than emptying")

    class D:
        def __init__(self, v):
            self.v = v

        def get(self, s):
            return self.v.get(s)

    ck(len(window_vals(D({s: 1.0 for s in range(940, 1000)}), 1000)) == 60,
       "a full window yields 60 prints")
    ck(window_vals(D({999: 1.0}), 1000) == [1.0],
       "and the last second is inside the window, the close itself is not")
    print("cdcchain selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    insts = cdcedge.load_instruments()
    if not insts:
        print("loaded nothing -- no CDNA instrument tape yet")
        return 0

    # group by (coin, period code) and order by period index
    chains = collections.defaultdict(dict)
    for sym, r in insts.items():
        att = (r.get("event_details") or {}).get("attributes") or {}
        try:
            pi = int(att.get("PERIOD_INDEX"))
            strike = float(att.get("STRIKE_PRICE"))
        except (TypeError, ValueError):
            continue
        close = cdcedge.parse_close(att.get("CLOSE_TIME"))
        opent = cdcedge.parse_close(att.get("OPEN_TIME"))
        coin = r.get("base_ccy")
        if not close or coin not in cdcedge.COIN_INDEX:
            continue
        # PERIOD_CODE DOES NOT IDENTIFY THE CHAIN. The first version grouped on
        # it and produced "consecutive" pairs whose closes were 55 minutes or
        # MINUS 10 minutes apart -- 5-minute and 15-minute contracts share the
        # code "I" and their PERIOD_INDEX counters run independently. Those
        # bogus pairs carried the worst errors in the table and would have been
        # read as feed noise. The duration of the window is what separates the
        # ladders, so it is part of the key, and the pair is checked below.
        dur = (close - opent) if opent else None
        if not dur:
            continue
        key = (coin, dur, att.get("STRIKE_INDEX"))
        chains[key][pi] = (close, opent, strike, sym, dur)

    idx = cdcedge.idxload.load(sorted({cdcedge.COIN_INDEX[c]
                                       for (c, _, _) in chains}), verbose=False)

    rows = []
    for (coin, code, si), byidx in sorted(chains.items()):
        D = idx.get(cdcedge.COIN_INDEX[coin])
        if D is None:
            continue
        for pi in sorted(byidx):
            if pi + 1 not in byidx:
                continue
            close, opent, strike, sym, dur = byidx[pi]
            nclose, nopen, nstrike, nsym, ndur = byidx[pi + 1]
            # THE PAIR MUST ACTUALLY BE BACK TO BACK. Consecutive PERIOD_INDEX
            # is not enough on its own -- see the key comment above.
            if nopen != close or ndur != dur:
                continue
            if close > (D.base + D.n) - 2:
                continue
            vals = window_vals(D, close)
            if len(vals) < 54:
                continue
            mean60 = sum(vals) / len(vals)
            trim = trimmed_mean(vals)
            spot = D.get(close - 1)
            rows.append({
                "coin": coin, "code": code, "pi": pi, "mins": (nclose - close) / 60.0,
                "strike_next": nstrike,
                "e_mean": 1e4 * (mean60 - nstrike) / nstrike,
                "e_trim": 1e4 * (trim - nstrike) / nstrike,
                "e_spot": (1e4 * (spot - nstrike) / nstrike) if spot else None,
            })
    if not rows:
        print("no consecutive pair has a settled index window yet -- the")
        print("recorder needs to span at least two closes of one coin.")
        return 0

    print("\nDoes strike(N+1) equal what OUR feed says window N settled at?")
    print("Error in basis points -- 1 bp is one hundredth of one percent.\n")
    print("  %-5s %-6s %6s %14s %9s %9s %9s"
          % ("coin", "period", "index", "their strike", "60s mean", "trimmed", "last tick"))
    print("  " + "-" * 74)
    for r in sorted(rows, key=lambda r: (r["coin"], r["pi"]))[:40]:
        print("  %-5s %-6s %6d %14.4f %8.1f %8.1f %9s"
              % (r["coin"], "%gmin" % r["mins"], r["pi"], r["strike_next"],
                 r["e_mean"], r["e_trim"],
                 ("%.1f" % r["e_spot"]) if r["e_spot"] is not None else "-"))

    def summarise(field, label):
        e = [abs(r[field]) for r in rows if r[field] is not None]
        if not e:
            return
        e.sort()
        print("  %-22s median %6.2f bp   worst %7.2f bp   under 5 bp: %d of %d"
              % (label, e[len(e) // 2], e[-1], sum(1 for x in e if x < 5), len(e)))

    print("\n  %d consecutive pairs scored." % len(rows))
    summarise("e_mean", "60-second mean")
    summarise("e_trim", "60-second trimmed")
    summarise("e_spot", "last tick only")
    best = min(("e_mean", "e_trim", "e_spot"),
               key=lambda f: statistics.median([abs(r[f]) for r in rows
                                                if r[f] is not None] or [1e9]))
    print("\n  Closest fit: %s." % best)
    print("  A median well under 5 bp means our feed IS their index for pricing")
    print("  purposes. A median in the hundreds means the strikes do not chain")
    print("  off a settlement we can see, and this venue cannot be priced from here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
