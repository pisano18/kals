"""READ-ONLY: every BRTI gap in the last N hourly files, with timestamps."""
import gzip, json, glob, os, sys, time
TAPE = r"C:\kals\kalshi_data\cfbenchmarks_value"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
files = sorted(glob.glob(os.path.join(TAPE, "*.jsonl.gz")))[-n:]
last = None; out = []; bad = []
for fn in files:
    ok = True
    try:
        with gzip.open(fn, "rt", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try: d = json.loads(ln)
                except Exception: continue
                m = d.get("msg") or {}
                if m.get("index_id") != "BRTI": continue
                data = m.get("data")
                try:
                    data = json.loads(data) if isinstance(data,str) else (data or {})
                    s = int(data["time"]) // 1000
                except Exception: continue
                if last is not None and s > last + 1:
                    out.append((last, s - last - 1, os.path.basename(fn)))
                if last is None or s > last: last = s
    except Exception as e:
        ok = False; bad.append((os.path.basename(fn), str(e)[:70]))
print(f"BRTI, {len(files)} files, {os.path.basename(files[0])}..{os.path.basename(files[-1])}")
for b in bad: print("  UNREADABLE FILE:", b)
print(f"  {'after (UTC)':<22}{'gap_s':>7}   file")
for st, g, fn in out:
    print(f"  {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(st)):<22}{g:>7}   {fn}")
