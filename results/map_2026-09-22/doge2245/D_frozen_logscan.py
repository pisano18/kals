"""How big is the blind window, on our own live runs?

Two counts, both from results/pinrun-live-*.jsonl only (our own fills, never
the tape):

 1. HELD-AND-HEDGED SECONDS -- the seconds in which a position was fully
    covered and therefore skipped at pinrun.py 10967 before the K3 index
    check at 11021. In those seconds no record can say whether the index was
    printing.
 2. INDEX-STALE LOOKS THAT OVERLAP A HOLD -- the entry path's own
    `refused gate=index_stale` (11851), matched to the same ticker's hold
    window, which is the only independent witness we have.
"""
import json
import glob
import os
import datetime
import collections


def ts(t):
    return int(datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ")
               .replace(tzinfo=datetime.timezone.utc).timestamp())


def main():
    files = sorted(glob.glob(r"C:\kals-repo\results\pinrun-live-*.jsonl"))
    holds = {}          # (run, ticker, close_s) -> [first fill second, close_s]
    hedge_full = {}     # (run, ticker, close_s) -> earliest tau fully covered
    stale = []          # (run, ticker, second, age_s)
    n_runs = 0
    for f in files:
        run = os.path.basename(f)
        n_runs += 1
        entry_n = collections.Counter()
        hedge_n = collections.Counter()
        close_of = {}
        for ln in open(f, encoding="utf-8", errors="replace"):
            if '"kind"' not in ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:                                 # noqa: BLE001
                continue
            k, tk = d.get("kind"), d.get("ticker")
            if k == "order" and (d.get("filled") or 0) > 0 and tk:
                sec = ts(d["t"])
                cs = sec + int(d.get("tau_at_send") or 0)
                close_of[(run, tk)] = cs
                key = (run, tk, cs)
                entry_n[key] += float(d["filled"])
                h = holds.setdefault(key, [sec, cs])
                h[0] = min(h[0], sec)
            elif k == "hedge" and (d.get("n") or 0) > 0 and tk:
                cs = close_of.get((run, tk))
                if cs is None:
                    continue
                key = (run, tk, cs)
                hedge_n[key] += float(d["n"])
                if (hedge_n[key] >= entry_n[key] - 1e-9
                        and key not in hedge_full):
                    hedge_full[key] = int(d.get("tau") or 0)
            elif (k == "refused" and d.get("gate") == "index_stale" and tk):
                stale.append((run, tk, ts(d["t"]), d.get("age_s")))
    blind = sorted(v for v in hedge_full.values() if v >= 1)
    print("live runs read:", n_runs)
    print("held markets (>=1 entry fill):", len(holds))
    print("markets fully hedged before the close:", len(blind))
    if blind:
        print("  seconds each one then spent unwatchable (tau at full cover):")
        print("   min %d  median %d  p90 %d  max %d  total %d seconds"
              % (blind[0], blind[len(blind) // 2],
                 blind[int(len(blind) * 0.9)], blind[-1], sum(blind)))
        print("  distribution:", dict(collections.Counter(blind)))
    print("entry index_stale looks recorded:", len(stale))
    hit = 0
    for run, tk, sec, age in stale:
        for (r2, t2, cs), (a, b) in holds.items():
            if r2 == run and t2 == tk and a <= sec <= b:
                hit += 1
                print("   OVERLAP:", run, tk, sec, "age_s", age)
    print("index_stale looks that fell inside a hold of the SAME ticker:", hit)


if __name__ == "__main__":
    main()
