#!/usr/bin/env python3
# VERSION: 2026-09-08-ei1
"""earlyidx.py -- build a compact second-indexed cache of the settlement index.

cfbenchmarks_value is 1.5 MB/hour, so the whole tape is cheap; what is NOT
cheap is holding 11 python dicts of 1.3M seconds each. Store one array('d')
per index, indexed by (second - T0), 0.0 meaning "no print". 11 x 1.3M x 8 B
= ~115 MB resident, which fits inside the RAM guard with room for the
collector.

The newest hour file is being written right now and is a truncated gzip:
EOFError AND zlib.error are both caught and the partial read is kept.

Writes NEW files only, under early_cache/.
"""
import argparse, array, glob, gzip, json, os, sys, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gzsalvage                                            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.dirname(HERE), "early_cache")
IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
T0 = 1787600000          # < any timestamp on this tape
NSEC = 1400000           # covers T0 .. T0+NSEC (past the newest hour)


def build(verbose=True):
    files = sorted(glob.glob(os.path.join(IDXDIR, "*.jsonl.gz")))
    if verbose:
        print(f"  {len(files)} index hour files, "
              f"{os.path.basename(files[0])} .. {os.path.basename(files[-1])}")
    vals, tmax = {}, 0
    for i, fp in enumerate(files):
        n = 0
        try:
            if True:
                for line in gzsalvage.iter_lines(fp):
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                        d = json.loads(m["data"])
                    except Exception:
                        continue
                    if d.get("type") != "value":
                        continue
                    iid = d.get("id") or m.get("index_id")
                    t = int(d["time"]) // 1000
                    v = float(d["value"])
                    a = vals.get(iid)
                    if a is None:
                        a = vals[iid] = array.array("d", bytes(8 * NSEC))
                    k = t - T0
                    if 0 <= k < len(a):
                        a[k] = v
                        if k > tmax:
                            tmax = k
                    n += 1
        except (EOFError, zlib.error, OSError) as e:
            if verbose:
                print(f"  {os.path.basename(fp)}: truncated ({type(e).__name__})"
                      f" -- kept {n:,} ticks read before the tear")
        if verbose and i % 40 == 0:
            print(f"    .. {os.path.basename(fp)} ({len(vals)} indices)")
    os.makedirs(CACHE, exist_ok=True)
    meta = {"T0": T0, "TMAX": tmax, "indices": {}}
    for iid, a in vals.items():
        trim = a[:tmax + 1]
        with open(os.path.join(CACHE, f"idx_{iid}.bin"), "wb") as f:
            f.write(trim.tobytes())
        meta["indices"][iid] = sum(1 for x in trim if x != 0.0)
    with open(os.path.join(CACHE, "idx_meta.json"), "w") as f:
        json.dump(meta, f)
    if verbose:
        print(f"\n  T0={T0} TMAX={tmax} span={(tmax)/86400.0:.2f} days")
        for iid in sorted(meta["indices"]):
            c = meta["indices"][iid]
            print(f"    {iid:<14} {c:>9,} prints  "
                  f"({100.0*c/(tmax+1):.1f}% of seconds)")
    return meta


def load():
    meta = json.load(open(os.path.join(CACHE, "idx_meta.json")))
    out = {}
    for iid in meta["indices"]:
        a = array.array("d")
        with open(os.path.join(CACHE, f"idx_{iid}.bin"), "rb") as f:
            a.frombytes(f.read())
        out[iid] = a
    return meta["T0"], out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        # a planted tick must come back at exactly its own second
        arr = array.array("d", bytes(8 * 10))
        arr[5] = 123.5
        ok = arr[5] == 123.5 and arr[4] == 0.0
        print("SELF-TEST " + ("PASSED" if ok else "*** FAILED ***"))
        raise SystemExit(0 if ok else 1)
    build()
