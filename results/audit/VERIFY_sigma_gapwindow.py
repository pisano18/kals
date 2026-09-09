"""READ-ONLY audit probe. Two questions, measured, nothing written outside here.

Q1. Does the REAL cfbenchmarks_value stream actually contain multi-second
    gaps?  Measured on the collector's own tape (read only).
Q2. With the LIVE arguments, is there a window in which partial() ACCEPTS
    while sigma() is still sampling pre-gap tape?  Measured by driving the
    real IndexWS through its real ingest path (on_frame), not by writing
    self.ticks directly, so the 1200-second deque is exercised.
"""
import gzip, json, os, sys, glob, collections, math, random

sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"
import pinrun

TAPE = r"C:\kals\kalshi_data\cfbenchmarks_value"

def q1(nfiles=6):
    print("=" * 78)
    print("Q1. REAL GAPS in the collector's cfbenchmarks_value tape")
    print("=" * 78)
    files = sorted(glob.glob(os.path.join(TAPE, "*.jsonl.gz")))[-nfiles:]
    secs = collections.defaultdict(set)
    for fn in files:
        try:
            with gzip.open(fn, "rt", encoding="utf-8", errors="replace") as fh:
                for ln in fh:
                    try:
                        d = json.loads(ln)
                    except Exception:
                        continue
                    m = d.get("msg") or {}
                    iid = m.get("index_id")
                    if not iid:
                        continue
                    data = m.get("data")
                    try:
                        data = json.loads(data) if isinstance(data, str) else (data or {})
                        secs[iid].add(int(data["time"]) // 1000)
                    except Exception:
                        continue
        except Exception as e:
            print(f"  READ FAILED {os.path.basename(fn)}: {e}")
    print(f"  files read: {[os.path.basename(f) for f in files]}")
    print(f"  {'index':<14}{'seconds':>9}{'span_s':>9}{'gaps>=5s':>10}"
          f"{'gaps>=30s':>11}{'max_gap_s':>11}")
    for iid in sorted(secs):
        s = sorted(secs[iid])
        if len(s) < 2:
            continue
        gaps = [s[i] - s[i-1] - 1 for i in range(1, len(s)) if s[i] - s[i-1] > 1]
        g5 = sum(1 for g in gaps if g >= 5)
        g30 = sum(1 for g in gaps if g >= 30)
        print(f"  {iid:<14}{len(s):>9}{s[-1]-s[0]:>9}{g5:>10}{g30:>11}"
              f"{(max(gaps) if gaps else 0):>11}")
    return secs

def q2():
    print()
    print("=" * 78)
    print("Q2. THE REACHABLE WINDOW, driven through the real on_frame ingest")
    print("=" * 78)
    C = 1_000_000
    def frame(iid, sec, val):
        return {"type": "cfbenchmarks_value",
                "msg": {"index_id": iid,
                        "data": json.dumps({"value": f"{val:.6f}",
                                            "time": sec * 1000})}}
    for tau in (30, 20, 3):
        for fresh in (0, 15, 31, 45, 58, 100, 200, 301):
            idx = pinrun.IndexWS(["G"])
            random.seed(7)
            v = 100.0
            now = C - tau
            gap_end = now - fresh          # last pre-gap second is gap_end-240
            # 900 s of quiet tape ending 240 s before gap_end
            for s in range(gap_end - 240 - 900, gap_end - 240):
                v += random.gauss(0, 0.01)
                idx.on_frame(frame("G", s, v))
            # fresh tape at 5x vol, `fresh`+1 seconds up to and including now
            for s in range(gap_end, now + 1):
                v += random.gauss(0, 0.05)
                idx.on_frame(frame("G", s, v))
            p = idx.partial("G", C, now)
            sg = idx.sigma("G")
            secs = sorted(idx.ticks["G"])[-pinrun.SIGMA_WIN:]
            pre = sum(1 for s in secs if s < gap_end)
            held = len(idx.ticks["G"])
            ratio = (0.05 / sg) if sg else float("nan")
            print(f"  tau={tau:<3} fresh={fresh:<4} held={held:<5} "
                  f"partial={'ACCEPT' if p else 'refuse':<6} "
                  f"sigma={'None' if sg is None else f'{sg:.5f}':<8} "
                  f"pre/win={pre:>3}/{len(secs):<3} "
                  f"understated={'n/a' if sg is None else f'{ratio:.2f}x'}")
        print()

if __name__ == "__main__":
    q1()
    q2()
