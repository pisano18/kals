"""One world of a golden replay, in its own process (replay.py starts it with PYTHONHASHSEED=0). Never imported by
production code.

    gl_child.py --fixture F --code C --world W --work DIR --out DIR [--only REGEX]

DIR (--work) is the world's scratch copy already prepared by replay.py: DIR/repo/results, DIR/repo/boot_all.ps1,
DIR/research/<data files>, DIR/kals. The fence is installed before anything from --code is imported.
"""
import argparse
import os
import re
import sys
import time
import types

sys.dont_write_bytecode = True
GOLDEN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, GOLDEN)
import gl_common as C          # noqa: E402
import gl_fence                # noqa: E402
import gl_worlds               # noqa: E402


def open_world(fixture, code, world, work, out):
    """Build one world in this process: the recorded machine, the fence (installed BEFORE --code is imported), the fake
    kauth, the code under test, the seams, the cache snapshot and the shared Ledger. None when pinphone cannot be
    imported (meta.json says why). shadow.py builds its worlds with this too."""
    t_start = time.perf_counter()
    fx = os.path.abspath(fixture)
    code = os.path.abspath(code)
    repo = os.path.dirname(code)
    work = os.path.abspath(work)
    out = os.path.abspath(out)
    os.makedirs(os.path.join(out, "cases"), exist_ok=True)

    # ---- the recorded machine (read before the fence) ----
    env = C.load_json(os.path.join(fx, "env.json"))
    health = C.load_json(os.path.join(fx, "health.json"))
    procs = C.load_json(os.path.join(fx, "procs.json"))
    kcalls_raw = C.load_json(os.path.join(fx, "kalshi.json"))
    kcalls = {k: (v["status"], v["body"]) for k, v in kcalls_raw.items()}
    env["_code"] = code
    T = gl_worlds.world_T(world, env)
    procs = gl_worlds.procs_for(world, procs, env)

    # ---- the fence: every real data path -> this world's copy ----
    W_res = os.path.join(work, "repo", "results")
    maps = [(os.path.join(repo, "results"), W_res), (r"C:\kals-repo\results", W_res),
            (os.path.join(repo, "boot_all.ps1"), os.path.join(work, "repo", "boot_all.ps1")),
            (r"C:\kals-repo\boot_all.ps1", os.path.join(work, "repo", "boot_all.ps1")),
            (r"C:\kals", os.path.join(work, "kals"))]
    rdata = os.path.join(work, "research")
    for root, _dirs, files in os.walk(rdata):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), rdata)
            maps.append((os.path.join(code, rel), os.path.join(rdata, rel)))
            maps.append((os.path.join(r"C:\kals-repo\research", rel), os.path.join(rdata, rel)))
    mpl = os.environ.get("MPLCONFIGDIR") or os.path.join(work, "mpl")
    tmp = os.environ.get("TMP") or os.path.join(work, "tmp")
    deny = [repo + "\\", "C:\\kals-repo\\", "C:\\kals\\", "C:\\kals-live", "C:\\kals-golden-base\\",
            os.path.join(os.path.expanduser("~"), ".ssh") + "\\"]
    fence = gl_fence.Fence("replay", maps=maps, allow_write=[work, out, mpl, tmp], allow_read=[code, GOLDEN], deny=deny)
    with open(os.path.join(fx, "manifest.json"), encoding="utf-8") as fh:
        man = __import__("json").load(fh)
    tops = {"results": W_res, "repo": os.path.join(work, "repo"), "research": rdata, "kals": os.path.join(work, "kals")}
    for rel, v in man.items():
        if isinstance(v, dict) and v.get("mode") == "placeholder" and rel.partition("/")[0] in tops:
            top, _, rest = rel.partition("/")
            fence.standins.add(os.path.normcase(os.path.join(tops[top], *rest.split("/"))))
    clock = gl_fence.Clock(T)
    gl_fence.install(fence)
    gl_fence.install_clock(clock)

    import gl_cases                                             # noqa: E402
    store = gl_cases.KalshiStore(kcalls, gl_worlds.kalshi_mode(world))
    sys.modules["kauth"] = gl_cases.fake_kauth(store)

    # ---- the code under test ----
    sys.path.insert(0, code)
    mods = {}
    import_err = {}
    for name in ("pindesk", "botstats", "pinphone", "tgcharts"):
        try:
            mods[name] = __import__(name)
        except Exception as e:                                  # noqa: BLE001
            import traceback
            import_err[name] = traceback.format_exc()
    if "pinphone" not in mods:
        C.dump_json(os.path.join(out, "meta.json"), {"world": world, "import_error": import_err}, codec=False)
        print(import_err)
        return None
    norm = C.Normaliser([(code, "<CODE>"), (repo, "<REPO>"), (r"C:\kals-repo", "<REPO>"), (work, "<WORK>"),
                         (out, "<OUT>"), (fx, "<FIXTURE>")])
    rt = gl_cases.Runtime(fence, clock, env, health, procs, store, "replay", out, norm,
                          cfg_path=r"C:\kals\telegram.json")
    rt.mods = mods
    gl_cases.apply_seams(rt)
    gl_cases.snapshot_caches(rt)
    led = mods["pindesk"].Ledger()
    t_led = time.perf_counter()
    led.refresh()
    rt.ledger = led
    led_s = time.perf_counter() - t_led                       # (the cache snapshot is from right after import)
    fence.track_root = os.path.normcase(work)      # from here on, a case's writes in the scratch copy are undone after it
    fence.saved = {}
    return types.SimpleNamespace(rt=rt, store=store, fence=fence, T=T, procs=procs, import_err=import_err, led_s=led_s,
                                 t_start=t_start, out=out, W_res=W_res, norm=norm, fx=fx, code=code, mods=mods)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--code", required=True)
    ap.add_argument("--world", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None, help="regex over case ids")
    ap.add_argument("--repeat", type=int, default=1, help="run each case N times in this process (flakiness check)")
    a = ap.parse_args()
    w = open_world(a.fixture, a.code, a.world, a.work, a.out)
    if w is None:
        return 3
    rt, store, fence, T, procs, import_err, led_s, t_start = (w.rt, w.store, w.fence, w.T, w.procs, w.import_err,
                                                               w.led_s, w.t_start)
    out, W_res, norm, fx, code = w.out, w.W_res, w.norm, w.fx, w.code
    import gl_cases                                             # noqa: E402  (imported by open_world, after the fence)
    if os.environ.get("GOLDEN_MPL_TRACE"):          # debugging a chart diff: every drawing call's data, to a file
        _mpl_trace(os.path.join(out, "mpl_trace.txt"))
    cases = gl_cases.case_list(rt)
    if a.only:
        rx = re.compile(a.only)
        cases = [c for c in cases if rx.search(c[0])]
    times, status, flaky = {}, {}, []
    for case in cases:
        res, secs, trace = gl_cases.run_case(rt, case)
        for _k in range(max(0, a.repeat - 1)):      # --repeat N: the same case again in this process; any change = flaky
            again, _s, _t = gl_cases.run_case(rt, case)
            if C.canon(again) != C.canon(res):
                flaky.append(case[0])
                print("golden FLAKY (in one process): %s" % case[0], flush=True)
                break
        times[case[0]] = round(secs, 3)
        status[case[0]] = res["status"]
        with open(os.path.join(out, "cases", C.case_file(case[0])), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(C.canon(res) + "\n")
        if trace:
            with open(os.path.join(out, "harness_errors.txt"), "a", encoding="utf-8") as fh:
                fh.write("== %s\n%s\n" % (case[0], trace))
        print("golden %-8s %6.2fs %s" % (res["status"], secs, case[0]), flush=True)
    import matplotlib
    import numpy
    meta = {"world": a.world, "desc": gl_worlds.WORLDS[a.world]["desc"], "T": T,
            "T_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(T)), "kalshi": store.mode,
            "procs_rows": None if procs is None else len(procs), "missing_seams": rt.missing_seams,
            "import_errors": import_err, "python": sys.version.split()[0], "matplotlib": matplotlib.__version__,
            "numpy": numpy.__version__, "ledger_refresh_s": round(led_s, 2),
            "seconds": round(time.perf_counter() - t_start, 2), "case_seconds": times, "status": status,
            "failed": sorted(k for k, v in status.items() if v != "ok"), "cases": len(cases), "flaky": flaky,
            "fixture": os.path.basename(fx.rstrip("\\/")), "code": code}
    C.dump_json(os.path.join(out, "meta.json"), meta, codec=False)
    try:
        with open(os.path.join(W_res, "pinphone.log"), encoding="utf-8", errors="replace") as fh:
            log = fh.read()
        with open(os.path.join(out, "pinphone.log"), "w", encoding="utf-8") as fh:
            fh.write(norm.s(log))
    except OSError:
        pass
    return 0


def _mpl_trace(path):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.axes import Axes
    fh = open(path, "w", encoding="utf-8")

    def wrap(name):
        orig = getattr(Axes, name)

        def w(self, *a, **k):
            fh.write("%s %r %r\n" % (name, [list(x) if hasattr(x, "__len__") and not isinstance(x, str) else x
                                           for x in a], sorted(k.items(), key=lambda kv: kv[0])))
            fh.flush()
            return orig(self, *a, **k)
        setattr(Axes, name, w)
    for n in ("plot", "step", "scatter", "bar", "barh", "fill_between", "text", "annotate", "axhline", "axvline",
              "set_xlim", "set_ylim", "axvspan", "axhspan"):
        if hasattr(Axes, n):
            wrap(n)


if __name__ == "__main__":
    sys.exit(main())
