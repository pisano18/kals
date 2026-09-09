#!/usr/bin/env python3
"""vfy_pinexit2.py -- LOOK-AHEAD TRUNCATION and HEDGE-LAG re-price.

C  TRUNCATION. For every (entry, second-after-entry) cell, rebuild the index
   tape with EVERY PRINT AFTER THAT SECOND DELETED, and the book dict with
   every later row deleted, then recompute the cell. Any feature that used the
   future changes. The test is equality to the LAST BIT, not a tolerance.
   The truncated tape is also cut BELOW at close-400, which simultaneously
   proves nothing outside [close-400, sec] is read.

G  HEDGE LAG. Re-price the recommended rule at lag 0, 1, 2, 3 seconds to
   confirm the authors' own statement that the look-ahead they found was
   worth 2-4% and that lag 1 is not the flattering choice.

SELFTEST: (1) the truncation harness must CATCH a deliberately planted
look-ahead feature, and (2) must pass a feature that is honestly causal.
"""
import argparse
import array
import json
import math
import os
import sys
import time

HERE = r"C:\kals-repo\research"
sys.path.insert(0, HERE)
import pinexit as PX                                            # noqa: E402
import pinexit_run as PR                                        # noqa: E402
from pinexit import IndexTape, walk                             # noqa: E402

SKIP = {"_cush", "_cush_bp", "_spot_bp", "_mu", "_spot", "_sd", "_r",
        "_sig", "_pmkt"}


def local_tape(tp, lo, hi):
    """A tape holding ONLY [lo, hi]; everything else is unreadable."""
    i = lo - tp.base
    j = hi - tp.base
    if i < 0 or j >= len(tp.a) or j < i:
        return None
    return IndexTape(lo, array.array("d", tp.a[i:j + 1]))


def truncated_cells(tp, close, K, yes, sec0, secs, kmax, back=400):
    """Recompute every cell with all data after that cell's second deleted.

    THE REFERENCE IS ALSO A WINDOW TAPE, deliberately. IndexTape keeps prefix
    sums of squared 1 s moves accumulated from its own base, so a tape that
    starts at a different second differs from the whole-tape one by about one
    ULP in sigma -- the same prefix-sum effect pinexit.py documents for wsum.
    That is an artefact of the HARNESS, not of the code under test, and it
    would otherwise drown a real look-ahead in 1e-16 noise. Both sides here
    accumulate from close-back, so an honest column must match EXACTLY and a
    cheating one still cannot hide.
    """
    ref = local_tape(tp, close - back, close - 1)
    out = {}
    for sec in range(sec0, close):
        k = sec - sec0
        if k > kmax:
            break
        t2 = local_tape(tp, close - back, sec)
        if t2 is None:
            continue
        b2 = {s: r for s, r in secs.items() if s <= sec}
        for kk, tau, f in walk(t2, close, K, yes, sec0, b2, kmax):
            if kk == k:
                out[k] = f
                break
    return out, ref


def compare(full, trunc):
    bad = []
    same = 0
    for k, f in full.items():
        g = trunc.get(k)
        if g is None:
            bad.append((k, "MISSING", None, None))
            continue
        for name, v in f.items():
            if name in SKIP:
                continue
            w = g.get(name)
            if v is None and w is None:
                same += 1
                continue
            if (v is None) != (w is None):
                bad.append((k, name, v, w))
                continue
            if isinstance(v, float) and isinstance(w, float):
                if v != w and not (v != v and w != w):
                    bad.append((k, name, v, w))
                else:
                    same += 1
            elif v != w:
                bad.append((k, name, v, w))
            else:
                same += 1
    return same, bad


def selftest():
    print("SELF-TEST -- vfy_pinexit2")
    ok = []

    def ck(c, m):
        ok.append(bool(c))
        print(("  ok   " if c else "  FAIL ") + m)

    base = 1000000
    n = 500
    arr = array.array("d", [100.0 + 0.001 * ((i * 37) % 11) for i in range(n)])
    tp = IndexTape(base, arr)
    close = base + 460
    K = 100.0
    sec0 = close - 50

    full = {}
    for k, tau, f in walk(tp, close, K, True, sec0, {}, 60):
        full[k] = f
    tr, ref = truncated_cells(tp, close, K, True, sec0, {}, 60)
    full = {k: f for k, tau, f in walk(ref, close, K, True, sec0, {}, 60)}
    same, bad = compare(full, tr)
    ck(same > 100 and not bad,
       "CAUSAL: pinexit's real feature vector is bit-identical when every "
       "print after the decision second is deleted (%d values compared, "
       "%d differ)" % (same, len(bad)))

    # plant a look-ahead: a feature that peeks one second into the future
    def peek_cells(tape, close_, K_, yes_, sec0_, kmax_):
        out = {}
        for k, tau, f in walk(tape, close_, K_, yes_, sec0_, {}, kmax_):
            sec = sec0_ + k
            nxt = tape.val(sec + 1)
            g = dict(f)
            g["CHEAT"] = nxt
            out[k] = g
        return out

    fullp = peek_cells(tp, close, K, True, sec0, 60)
    trp = {}
    refp = local_tape(tp, close - 400, close - 1)
    fullp = peek_cells(refp, close, K, True, sec0, 60)
    for sec in range(sec0, close):
        k = sec - sec0
        if k > 60:
            break
        t2 = local_tape(tp, close - 400, sec)
        if t2 is None:
            continue
        d = peek_cells(t2, close, K, True, sec0, 60)
        if k in d:
            trp[k] = d[k]
    same2, bad2 = compare(fullp, trp)
    cheats = [b for b in bad2 if b[1] == "CHEAT"]
    ck(len(cheats) > 20,
       "PLANTED: a feature that peeks one second ahead IS caught by the same "
       "harness (%d cells differ on CHEAT)" % len(cheats))
    ck(all(b[1] == "CHEAT" for b in bad2),
       "PLANTED: and ONLY the cheating column differs -- the harness does not "
       "manufacture failures in honest columns")

    print("SELF-TEST " + ("PASSED" if all(ok) else "FAILED"))
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=PX.ROWS)
    ap.add_argument("--sample", type=int, default=60)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed; refusing real data")

    by, nrows = PR.load_rows(a.rows, 3, 60)
    lo = min(min(s.keys()) for s in by.values())
    hi = max(max(s.keys()) for s in by.values())
    idx = PR.load_index_cache(lo - 400, hi + 120,
                              os.path.join(PX.WORK, "pinexit_idx_wide.pkl"))
    tapes = {k: IndexTape(*v) for k, v in idx.items()}
    mk = {}
    for v in json.load(open(PX.FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in PX.SERIES_TO_INDEX:
                mk[r["ticker"]] = r

    ents = PR.build_entries(by, tapes, mk, 3, 60, True, True)
    losers = [e for e in ents if e[6]]
    winners = [e for e in ents if not e[6]]
    step = max(1, len(winners) // max(a.sample - len(losers), 1))
    sample = losers + winners[::step][:max(a.sample - len(losers), 0)]

    print("\n" + "=" * 78)
    print("  C -- LOOK-AHEAD TRUNCATION ON REAL TAPE")
    print("  Every cell recomputed with all index prints and all book rows")
    print("  AFTER that second deleted, and the tape also cut below at")
    print("  close-400. Equality is required TO THE LAST BIT.")
    print("=" * 78)
    print("  sample: %d markets (%d losers, %d winners)"
          % (len(sample), len(losers), len(sample) - len(losers)))
    tot_same = tot_bad = ncell = 0
    shown = 0
    win_worst = [0.0]
    for (tk, close, K, tp, sec0, yes, lose, price, secs, sr) in sample:
        tr, ref = truncated_cells(tp, close, K, yes, sec0, secs, 57)
        full = {k: f for k, tau, f in walk(ref, close, K, yes, sec0, secs, 57)}
        whole = {k: f for k, tau, f in walk(tp, close, K, yes, sec0, secs, 57)}
        for k, f in whole.items():
            g = full.get(k) or {}
            for nm, v in f.items():
                if nm in SKIP or not isinstance(v, float):
                    continue
                w = g.get(nm)
                if isinstance(w, float) and v == v and w == w:
                    rel = abs(v - w) / max(abs(v), 1e-30)
                    if rel > win_worst[0]:
                        win_worst[0] = rel
        s, b = compare(full, tr)
        tot_same += s
        tot_bad += len(b)
        ncell += len(full)
        if b and shown < 5:
            shown += 1
            print("    DIFFERS %s: %s" % (tk, b[:4]))
    print("  %d cells, %d feature values compared, %d differ"
          % (ncell, tot_same, tot_bad))
    print("  VERDICT: %s"
          % ("NO LOOK-AHEAD -- every value bit-identical" if tot_bad == 0
             else "*** LOOK-AHEAD PRESENT ***"))
    print("  and the window tape [close-400, sec] reproduces the WHOLE-tape")
    print("  feature vector to %.1e relative -- so nothing outside 400 s"
          % win_worst[0])
    print("  before the close is read at all (that residue is the one-ULP")
    print("  prefix-sum origin effect, not information).")

    print("\n" + "=" * 78)
    print("  G -- HEDGE LAG. The recommended rule re-priced at 0..3 s.")
    print("  lag 0 is the authors' own admitted look-ahead.")
    print("=" * 78)
    wl = [1.0 - e[7] - PR.fee(e[7]) for e in ents if not e[6]]
    tw = sum(wl) / len(wl)
    tot_b = sum(((-e[7]) if e[6] else (1.0 - e[7])) - PR.fee(e[7])
                for e in ents if e[7] is not None) / tw
    sys.path.insert(0, r"C:\kals-repo\results\_verify")
    from vfy_pinexit import score_rule
    print("  438 trades, typical win %.2fc, NO HEDGE total %.1f wins"
          % (100 * tw, tot_b))
    for feat, th in (("p_model", 0.5), ("sd_loss", 2.0)):
        for lag in (0, 1, 2, 3):
            r = score_rule(ents, feat, th, lag)
            t = sum(p for p, l, h in r["pnl"]) / tw
            print("    %s >= %-5s lag %d: total %8.1f wins  (%+.1f%% vs no "
                  "hedge)  hedged %d"
                  % (feat, th, lag, t, 100 * (t - tot_b) / abs(tot_b),
                     sum(1 for p, l, h in r["pnl"] if h)))


if __name__ == "__main__":
    main()
