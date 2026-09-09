#!/usr/bin/env python3
"""vfy_cliffunit.py -- is pinclose.cliff_test using the wrong unit?

pinclose builds its cliff cells from table(), which fills them with ROW counts
(tot[b] = rows, row-flips). cliff_test then compares the observed likelihood
ratio against a PARAMETRIC BOOTSTRAP that draws INDEPENDENT Bernoulli rows.
But rows inside one market share one settlement -- the project's own hard rule
4. If the observed LR is inflated by that clustering while the null is not,
every p-value from this test is anti-conservative, and the p = 0.007 floor
that appears on seven of nine cells is what an anti-conservative test looks
like.

TEST: build a world that is SMOOTH by construction and CLUSTERED by
construction -- each market contributes 9 perfectly correlated rows, one per
tau on pinclose's own grid -- and ask cliff_test whether there is a cliff.
There is not. Anything it finds is the clustering.

CONTROL: the same world with the same number of INDEPENDENT rows, where the
test must find nothing.

Then re-run the two real cells that mattered at the MARKET unit.
"""
import json
import math
import os
import random
import sys

sys.path.insert(0, r"C:\kals-repo\research")
import pinclose as PC                                        # noqa: E402

FULLTAPE = r"C:\kals\fulltape\markets.json"


def make_cells(nmkt, rows_per_mkt, ps, clustered, seed):
    """One cell per bucket. ps[b] = true per-MARKET flip probability."""
    rnd = random.Random(seed)
    cells = []
    for b, p in enumerate(ps):
        n = k = 0
        for _ in range(nmkt):
            if clustered:
                fl = rnd.random() < p
                n += rows_per_mkt
                k += rows_per_mkt if fl else 0
            else:
                for _ in range(rows_per_mkt):
                    n += 1
                    k += 1 if rnd.random() < p else 0
        cells.append((math.log(0.03 * (1.7 ** b)), n, k))
    return cells


def selftest():
    print("SELF-TEST -- vfy_cliffunit")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # smooth logistic truth, no step anywhere
    ps = []
    for b in range(6):
        lx = math.log(0.03 * (1.7 ** b))
        ps.append(1.0 / (1.0 + math.exp(-(-1.0 - 0.9 * lx))))
    ck(all(ps[i] > ps[i + 1] for i in range(len(ps) - 1)),
       f"PLANT: a strictly smooth decreasing truth "
       f"{', '.join('%.3f' % p for p in ps)} -- no step exists in it")
    ind = make_cells(400, 9, ps, clustered=False, seed=1)
    r_ind = PC.cliff_test(ind, nboot=120, seed=2)
    ck(r_ind is not None and r_ind["p"] > 0.05,
       f"CONTROL, independent rows: cliff_test correctly finds no cliff "
       f"(p = {r_ind['p']:.3f})")
    ck(sum(c[1] for c in ind) == sum(c[1] for c in
                                     make_cells(400, 9, ps, True, 1)),
       "the clustered world has exactly the same number of rows, so any "
       "difference is the correlation and not the sample size")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def main():
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    print("\n" + "=" * 74)
    print("  IS cliff_test's UNIT WRONG?  smooth truth, clustered rows")
    print("=" * 74)
    ps = []
    for b in range(6):
        lx = math.log(0.03 * (1.7 ** b))
        ps.append(1.0 / (1.0 + math.exp(-(-1.0 - 0.9 * lx))))
    print("  true per-market flip prob by bucket: "
          + ", ".join("%.4f" % p for p in ps))
    print(f"  {'world':>34}{'rows':>9}{'p from cliff_test':>20}")
    for seed in (11, 12, 13, 14, 15):
        cl = make_cells(400, 9, ps, clustered=True, seed=seed)
        r = PC.cliff_test(cl, nboot=150, seed=seed + 100)
        print(f"  {'CLUSTERED (9 rows per market)':>34}"
              f"{sum(c[1] for c in cl):>9,}{r['p']:>20.3f}")
    for seed in (11, 12, 13):
        ind = make_cells(400, 9, ps, clustered=False, seed=seed)
        r = PC.cliff_test(ind, nboot=150, seed=seed + 200)
        print(f"  {'INDEPENDENT (same row count)':>34}"
              f"{sum(c[1] for c in ind):>9,}{r['p']:>20.3f}")
    print("  A smooth world must give p > 0.05. Any cell that does not is the")
    print("  test reading clustering as a cliff.")

    # ---- the real cells, re-run at the MARKET unit ---------------------
    print("\n" + "=" * 74)
    print("  THE REAL CELLS, RE-RUN AT THE MARKET UNIT")
    print("=" * 74)
    print("  loading index tape ...", flush=True)
    idx = PC.load_index(PC.index_files(), verbose=False)
    mk_all = json.load(open(FULLTAPE, encoding="utf-8"))
    markets = [r for v in mk_all.values() for r in v
               if r["series"] in PC.SERIES_TO_INDEX]
    ip = PC.build_index_pop(idx, markets, (5, 10, 15, 20, 25, 30, 40, 50, 60),
                            verbose=False)
    ipc = [r for r in ip if r["pf"] <= PC.PIN_P]
    print(f"  {len(ip):,} rows, {len(ipc):,} model-confident")

    for key, edges in (("bps", PC.BPS_EDGES), ("cr300", PC.CR_EDGES)):
        for lab, rws in (("all rows", ip), ("model-confident", ipc)):
            nb = len(edges) + 1
            rowc = [[0, 0] for _ in range(nb)]
            mk = [set() for _ in range(nb)]
            mkf = [set() for _ in range(nb)]
            for r in rws:
                b = PC.bucket(r.get(key), edges)
                if b is None:
                    continue
                rowc[b][0] += 1
                rowc[b][1] += 1 if r["flip"] else 0
                mk[b].add((r["tk"], r["close"]))
                if r["flip"]:
                    mkf[b].add((r["tk"], r["close"]))
            cell_row, cell_mkt = [], []
            for b in range(nb):
                lo = edges[0] * 0.5 if b == 0 else edges[b - 1]
                hi = edges[-1] * 2 if b == nb - 1 else edges[b]
                lx = math.log(max(1e-6, math.sqrt(lo * hi)))
                if rowc[b][0]:
                    cell_row.append((lx, rowc[b][0], rowc[b][1]))
                if mk[b]:
                    cell_mkt.append((lx, len(mk[b]), len(mkf[b])))
            rr = PC.cliff_test(cell_row, nboot=150)
            rm = PC.cliff_test(cell_mkt, nboot=150)
            print(f"  {key:>6} {lab:>16}:  ROW unit  LR {rr['lr']:>7.2f}  "
                  f"p {rr['p']:.3f}   |   MARKET unit  LR {rm['lr']:>7.2f}  "
                  f"p {rm['p']:.3f}")
    print("\n  DONE.")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(0 if selftest() else 1)
    main()
