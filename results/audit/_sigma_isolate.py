"""READ-ONLY. Isolate the BUG's OWN contribution to sigma error.

Compares, on the same synthetic tape:
  buggy   = pinrun.IndexWS.sigma()             (last 300 PRESENT seconds)
  fixed   = the proposed wall-clock window     (seconds in [now-300, now])
  truth   = the post-gap regime's sigma
for a range of REAL gap lengths, at the earliest moment partial() accepts.
Also runs a NO-REGIME-CHANGE control: if vol is unchanged across the gap the
bug must be harmless, or the test is measuring something else.
"""
import os, sys, json, math, random
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"
import pinrun

WIN = pinrun.SIGMA_WIN

def fixed_sigma(idx, iid, now_s):
    d = dict(idx.ticks.get(iid) or {})
    lo = now_s - WIN
    secs = sorted(s for s in d if lo <= s <= now_s)
    diffs = [d[secs[i]] - d[secs[i-1]] for i in range(1, len(secs))
             if secs[i] - secs[i-1] == 1]
    if len(diffs) < 20:
        return None, len(secs)
    mu = sum(diffs)/len(diffs)
    return math.sqrt(sum((x-mu)**2 for x in diffs)/(len(diffs)-1)), len(secs)

def frame(iid, sec, val):
    return {"type": "cfbenchmarks_value",
            "msg": {"index_id": iid,
                    "data": json.dumps({"value": f"{val:.8f}", "time": sec*1000})}}

def run(sig_pre, sig_post, label):
    C = 1_000_000
    print(f"\n{label}   pre-gap sigma {sig_pre}  post-gap sigma {sig_post}")
    print(f"  {'gap_s':>6}{'tau':>5}{'fresh':>7}{'partial':>9}"
          f"{'buggy':>10}{'x_true':>8}{'fixed':>10}{'x_true':>8}"
          f"{'fix_n':>7}{'bug_adds':>10}")
    for G in (10, 27, 31, 144, 240, 300):
        for tau, fresh in ((30, 31), (3, 58)):
            idx = pinrun.IndexWS(["G"])
            random.seed(3)
            v = 100.0
            now = C - tau
            gap_end = now - fresh
            for s in range(gap_end - G - 900, gap_end - G):
                v += random.gauss(0, sig_pre); idx.on_frame(frame("G", s, v))
            for s in range(gap_end, now + 1):
                v += random.gauss(0, sig_post); idx.on_frame(frame("G", s, v))
            p = idx.partial("G", C, now)
            b = idx.sigma("G")
            f, fn = fixed_sigma(idx, "G", now)
            xb = sig_post/b if b else float('nan')
            xf = (sig_post/f) if f else float('nan')
            adds = (xb/xf) if (b and f) else float('nan')
            print(f"  {G:>6}{tau:>5}{fresh:>7}"
                  f"{('ACCEPT' if p else 'refuse'):>9}"
                  f"{b:>10.5f}{xb:>8.2f}"
                  f"{(f if f else float('nan')):>10.5f}{xf:>8.2f}"
                  f"{fn:>7}{adds:>10.2f}")

run(0.01, 0.05, "A. 5x VOL JUMP at the gap (the finding's scenario)")
run(0.05, 0.05, "B. CONTROL -- no regime change (bug must be harmless)")
run(0.05, 0.01, "C. VOL COLLAPSE at the gap (bug OVERstates -> safe side)")
