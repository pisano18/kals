#!/usr/bin/env python3
"""_verify_pindraw3.py -- the 2026-09-09 case under the rule the AGGREGATE
result actually describes, plus feed-latency arithmetic.

pindrawcase.py asks what a CROSSING-triggered capped hedge would have done on
the -$52.60 close and answers "nothing -- the other side cost 48c by then".
But _verify_pindraw2 shows the aggregate tail benefit is bought by CHEAP
insurance, not by the crossing: 222 of 236 capped fills happen while the
projected settlement is still on our own side. So the rule to test on this close
is the cheap-insurance one: buy the other side any second it is offered at or
under the cap, whether or not anything has crossed.

Also measured here: how late the tape actually reaches us. Every price and index
value in pindraw is stamped with EXCHANGE time (ts_ms / data.time), but a live
loop can only act on RECEIVE time (_rx_ms). The gap is the part of "13 seconds
of lead" that is not ours.
"""
import argparse
import glob
import gzip
import json
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pindraw as PD                                          # noqa: E402
import pindrawcase as PC                                      # noqa: E402


def always(row, pos):
    return True


def selftest():
    print("SELF-TEST -- _verify_pindraw3")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # PLANTED: a 10c offer exists for 3 seconds after entry then vanishes to
    # 80c. ALWAYS-capped must take the 10c one; SPOT_CROSS, which only fires
    # after the vanish, must take nothing.
    rows = []
    for t in range(29, 0, -1):
        if t >= 27:
            rows.append((t, 101.0, 101.0, 100.0, 0.99, 0.5, 0.90, 0.92,
                         50.0, 50.0, 100))       # our side fine, other = 10c
        else:
            rows.append((t, 99.0, 99.0, 100.0, 0.02, 0.5, 0.20, 0.80,
                         50.0, 50.0, 100))       # crossed, other = 80c
    pos = {"tau": 30, "want": "yes", "price": 0.95, "n": 20.0}
    ha = PD.run_hedge(dict(pos), rows, always, max_px=0.10)[0]
    hs = PD.run_hedge(dict(pos), rows, PD.make_triggers()["SPOT_CROSS"][0],
                      max_px=0.10)[0]
    ck(sum(q for q, _ in ha) == 20.0 and hs == [],
       "planted: the cheap-insurance rule buys the 10c offer that existed "
       "BEFORE the crossing; the crossing-triggered rule gets nothing (%s / "
       "%s)" % (ha, hs))
    # NULL: no cheap offer ever -> neither buys anything
    dear = [(t, 99.0, 99.0, 100.0, 0.02, 0.5, 0.20, 0.80, 50.0, 50.0, 100)
            for t in range(29, 0, -1)]
    ck(PD.run_hedge(dict(pos), dear, always, max_px=0.10)[0] == [],
       "NULL: with nothing cheap on offer the cheap-insurance rule buys "
       "nothing and invents no saving")
    ck(PC.selftest(), "pindrawcase's own self-test passes")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def latency(channel, key, n_files=2):
    fs = sorted(glob.glob(os.path.join(PD.DATA, channel, "2026*.jsonl.gz")))
    fs = fs[-(n_files + 1):-1]
    d = []
    for fpath in fs:
        try:
            with gzip.open(fpath, "rt") as fh:
                for ln in fh:
                    try:
                        o = json.loads(ln)
                    except Exception:
                        continue
                    rx = o.get("_rx_ms")
                    if rx is None:
                        continue
                    m = o.get("msg") or {}
                    if key == "ts_ms":
                        t = m.get("ts_ms")
                    else:
                        try:
                            t = int(json.loads(m["data"])["time"])
                        except Exception:
                            continue
                    if t:
                        d.append(int(rx) - int(t))
        except (EOFError, zlib.error, OSError):
            pass
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    close_s = PC.CASE["close_s"]
    ix = PC.load_one_index(PC.CASE["iid"], close_s)
    if ix is None:
        raise SystemExit("index not in the tape window")
    ts = ix.settle(close_s)
    print("\n  tape settlement %.6f vs recorded %.6f (diff %.6f)"
          % (ts, PC.CASE["settle"], abs(ts - PC.CASE["settle"])))
    if abs(ts - PC.CASE["settle"]) > 1e-4:
        raise SystemExit("tape does not reproduce the recorded settlement")
    msgs = PC.load_one_market(PC.CASE["tk"], close_s)
    qs = PD.Quotes(close_s, msgs, PD.PANEL_TAU)
    rows = PD.build_panel({"close_s": close_s, "K": PC.CASE["K"]}, ix, qs,
                          PD.PANEL_TAU)
    base = sum(PD.leg_pnl(b[2], b[1], False) for b in PC.CASE["buys"])
    print("  unhedged %.2f" % base)

    print("\n== THE 09-09 CLOSE UNDER CHEAP INSURANCE (no trigger at all) ==")
    print("   %6s %8s %10s %12s   %s"
          % ("cap", "hedged", "result$", "vs -52.60", "fills (tau, px, qty)"))
    for cap in (0.05, 0.10, 0.15, 0.25):
        tot = 0.0
        hq = 0.0
        detail = []
        for tau, px, n in PC.CASE["buys"]:
            pos = {"tk": PC.CASE["tk"], "tau": tau, "want": PC.CASE["want"],
                   "price": px, "n": n}
            h = PD.run_hedge(dict(pos), rows, always, max_px=cap)[0]
            tot += PD.leg_pnl(n, px, False, h)
            hq += sum(q for q, _ in h)
            detail.append("[%s]" % ",".join("%.0f@%.3f" % (q, x)
                                            for q, x in h))
        print("   %5.0fc %8.1f %10.2f %+12.2f   %s"
              % (100 * cap, hq, tot, tot - base, " ".join(detail)))

    print("\n== FEED LATENCY: exchange stamp -> our receive (last 2 hours) ==")
    for ch, key in (("ticker", "ts_ms"), ("cfbenchmarks_value", "data.time")):
        d = latency(ch, key)
        if not d:
            print("   %-20s no messages" % ch)
            continue
        print("   %-20s n=%d  median %.0f ms  p90 %.0f ms  p99 %.0f ms"
              % (ch, len(d), PD.pct(d, 50), PD.pct(d, 90), PD.pct(d, 99)))


if __name__ == "__main__":
    main()
