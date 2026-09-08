#!/usr/bin/env python3
"""
pinfeat_np7_idx.py -- build a compact 1-second index cache from
kalshi_data/cfbenchmarks_value, ONCE, so the feature work can re-read it
cheaply.  READ-ONLY on the tape.  Writes only into --cache (a temp dir).

Layout per index_id:
    <cache>/idx_<ID>.f64   array('d'), NaN for a second with no print,
                           element i is the print stamped at t0 + i
    <cache>/meta.json      {"t0": .., "n": .., "ids": {..: count}}

The parse is done with str.find rather than json.loads (14M lines); a
--verify pass checks the fast parse against json.loads on a sample.
"""
import argparse, array, glob, gzip, json, math, os, sys, zlib

NAN = float("nan")


def iter_lines(fp):
    """Lines of a .jsonl.gz, tolerating a live/truncated tail."""
    try:
        with gzip.open(fp, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line
    except (EOFError, zlib.error, OSError):
        return


def fast_parse(line):
    """(index_id, time_ms, value) or None.  Mirrors replay.load_index."""
    i = line.find('"index_id":"')
    if i < 0:
        return None
    i += 12
    j = line.find('"', i)
    iid = line[i:j]
    # inner "data" is an escaped JSON string: \"time\":1788263996000
    k = line.find('\\"time\\":', j)
    if k < 0:
        return None
    k += 9
    m = k
    while m < len(line) and (line[m].isdigit() or line[m] in "-+."):
        m += 1
    try:
        tms = int(line[k:m])
    except ValueError:
        return None
    p = line.find('\\"value\\":\\"', m)
    if p < 0:
        return None
    p += 12
    q = line.find(chr(92), p)
    try:
        val = float(line[p:q])
    except ValueError:
        return None
    return iid, tms, val


def verify(data_dir, n=4000):
    files = sorted(glob.glob(os.path.join(data_dir, "cfbenchmarks_value",
                                          "*.jsonl.gz")))
    picks = [files[0], files[len(files)//3], files[2*len(files)//3], files[-2]]
    checked = bad = 0
    for fp in picks:
        c = 0
        for line in iter_lines(fp):
            f = fast_parse(line)
            try:
                d = json.loads(line)
                m = d.get("msg") or {}
                inner = m.get("data")
                inner = json.loads(inner) if isinstance(inner, str) else inner
                g = (m.get("index_id"), int(inner["time"]), float(inner["value"]))
            except Exception:
                g = None
            if f != g:
                bad += 1
                if bad < 4:
                    print("  MISMATCH", os.path.basename(fp), f, g)
            checked += 1
            c += 1
            if c >= n:
                break
    print(f"  fast_parse verified on {checked:,} lines from "
          f"{len(picks)} files: {bad} mismatches")
    return bad == 0


def hour_epoch(fp):
    """Epoch seconds of the hour a file name names: 20260825T04 -> ..."""
    import datetime as _dt
    b = os.path.basename(fp).split(".")[0]
    d = _dt.datetime(int(b[0:4]), int(b[4:6]), int(b[6:8]), int(b[9:11]),
                     tzinfo=_dt.timezone.utc)
    return int(d.timestamp())


def build(data_dir, cache):
    """One streaming pass; arrays allocated up front off the FILE NAMES so no
    14M-entry dict is ever held (that alone was ~1.4 GB)."""
    files = sorted(glob.glob(os.path.join(data_dir, "cfbenchmarks_value",
                                          "*.jsonl.gz")))
    if not files:
        print("  loaded nothing")
        return None
    t0 = hour_epoch(files[0]) - 3600
    n = hour_epoch(files[-1]) + 2 * 3600 - t0
    print(f"  {len(files)} hour files, grid t0={t0} n={n:,}s ({n/86400:.2f} d)")
    arrs, cnt, out_of_range = {}, {}, 0
    rows = 0
    for fi, fp in enumerate(files):
        for line in iter_lines(fp):
            r = fast_parse(line)
            if r is None:
                continue
            iid, tms, val = r
            i = tms // 1000 - t0
            if not (0 <= i < n):
                out_of_range += 1
                continue
            a = arrs.get(iid)
            if a is None:
                a = arrs[iid] = array.array("d", [NAN]) * n
                cnt[iid] = 0
            if a[i] != a[i]:
                cnt[iid] += 1
            a[i] = val
            rows += 1
        if fi % 40 == 0:
            print(f"    {fi}/{len(files)} rows={rows:,}", flush=True)
    print(f"  parsed {rows:,} prints, {out_of_range:,} outside the grid, "
          f"{len(arrs)} indices")
    os.makedirs(cache, exist_ok=True)
    meta = {"t0": t0, "n": n, "ids": {}}
    for iid, a in sorted(arrs.items()):
        with open(os.path.join(cache, f"idx_{iid}.f64"), "wb") as f:
            a.tofile(f)
        meta["ids"][iid] = cnt[iid]
        print(f"    {iid:>14}: {cnt[iid]:>9,} prints  "
              f"{100.0*cnt[iid]/n:5.1f}% grid coverage")
    with open(os.path.join(cache, "meta.json"), "w") as f:
        json.dump(meta, f)
    return meta


def load(cache, iid):
    meta = json.load(open(os.path.join(cache, "meta.json")))
    a = array.array("d")
    with open(os.path.join(cache, f"idx_{iid}.f64"), "rb") as f:
        a.fromfile(f, meta["n"])
    return meta["t0"], a


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=r"C:\kals\kalshi_data")
    ap.add_argument("--cache", default=r"C:\Users\Joe\AppData\Local\Temp\pinfeat_np7")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.verify:
        sys.exit(0 if verify(a.data) else 1)
    build(a.data, a.cache)
