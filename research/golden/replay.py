"""Golden replay: render every case of every world from a fixture with a given code tree, into an output folder that
compare.py checks against another. Never imported by production code.

    python research\\golden\\replay.py --fixture C:\\kals-golden\\fixtures\\<stamp> --code C:\\kals-golden-base\\research
                                      --out C:\\kals-golden\\expected\\<sha> [--world base --world empty-logs] [--jobs 2]

Each world runs in its own process (PYTHONHASHSEED=0, frozen clock, fence installed before import) on a scratch copy
of the fixture (mtimes restored from manifest.json). PNGs depend on the matplotlib build: record and compare on the
same machine.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

GOLDEN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, GOLDEN)
import gl_worlds               # noqa: E402


def copy_fixture(fx, work):
    """fixture -> work/repo/results, work/repo/<root files>, work/research, work/kals; every mtime from the fixture."""
    if os.path.exists(work):
        shutil.rmtree(work)
    pairs = [("results", os.path.join("repo", "results")), ("repo", "repo"), ("research", "research"), ("kals", "kals")]
    for src, dst in pairs:
        s = os.path.join(fx, src)
        if not os.path.isdir(s):
            os.makedirs(os.path.join(work, dst), exist_ok=True)
            continue
        for r, _dirs, files in os.walk(s):
            rel = os.path.relpath(r, s)
            td = os.path.normpath(os.path.join(work, dst, rel))
            os.makedirs(td, exist_ok=True)
            for f in files:
                shutil.copy2(os.path.join(r, f), os.path.join(td, f))
    with open(os.path.join(fx, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    for rel, v in man.items():
        if rel.startswith("_") or not isinstance(v, dict) or v.get("mtime") is None:
            continue
        top, _, rest = rel.partition("/")
        base = {"results": os.path.join(work, "repo", "results"), "repo": os.path.join(work, "repo"),
                "research": os.path.join(work, "research"), "kals": os.path.join(work, "kals")}.get(top)
        p = os.path.join(base, *rest.split("/")) if base else None
        if p and os.path.exists(p):
            os.utime(p, (v["mtime"], v["mtime"]))
    os.makedirs(os.path.join(work, "tmp"), exist_ok=True)


def run_world(world, a, env):
    work = os.path.join(a.work, world)
    out = os.path.join(a.out, world)
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    t0 = time.perf_counter()
    copy_fixture(a.fixture, work)
    gl_worlds.prepare(world, os.path.join(work, "repo", "results"), env)
    t_copy = time.perf_counter() - t0
    e = dict(os.environ)
    e.update(PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg", OPENBLAS_NUM_THREADS="1",
             MPLCONFIGDIR=a.mpl, TMP=os.path.join(work, "tmp"), TEMP=os.path.join(work, "tmp"),
             PYTHONIOENCODING="utf-8", TZ=e.get("TZ", ""))
    if not e["TZ"]:
        e.pop("TZ")
    for k in ("PYTHONPATH", "PYTHONSTARTUP", "PYTHONUTF8", "KALSHI_KEY_FILE"):
        e.pop(k, None)
    cmd = [a.python, "-u", os.path.join(GOLDEN, "gl_child.py"), "--fixture", a.fixture, "--code", a.code,
           "--world", world, "--work", work, "--out", out]
    if a.only:
        cmd += ["--only", a.only]
    if a.repeat > 1:
        cmd += ["--repeat", str(a.repeat)]
    t1 = time.perf_counter()
    with open(os.path.join(out, "stdout.txt"), "w", encoding="utf-8") as fh:
        rc = subprocess.run(cmd, cwd=work, env=e, stdout=fh, stderr=subprocess.STDOUT, timeout=a.timeout).returncode
    secs = time.perf_counter() - t1
    if not a.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    meta = {}
    try:
        with open(os.path.join(out, "meta.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        pass
    return world, {"rc": rc, "seconds": round(secs, 1), "copy_seconds": round(t_copy, 1), "cases": meta.get("cases"),
                   "failed": meta.get("failed"), "missing_seams": meta.get("missing_seams")}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--code", default=os.path.dirname(GOLDEN), help="the research folder of the tree under test")
    ap.add_argument("--out", required=True)
    ap.add_argument("--world", action="append", help="repeatable; default every world")
    ap.add_argument("--work", default=None, help="scratch folder (default <out>\\_work)")
    ap.add_argument("--mpl", default=None, help="matplotlib cache folder (default <out>\\..\\_mplcache)")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--only", default=None, help="regex over case ids")
    ap.add_argument("--repeat", type=int, default=1, help="run each case N times per process (flakiness check)")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--keep-work", action="store_true")
    a = ap.parse_args()
    a.fixture = os.path.abspath(a.fixture)
    a.code = os.path.abspath(a.code)
    a.out = os.path.abspath(a.out)
    a.work = os.path.abspath(a.work or os.path.join(a.out, "_work"))
    a.mpl = os.path.abspath(a.mpl or os.path.join(os.path.dirname(a.out), "_mplcache"))
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(a.mpl, exist_ok=True)
    if not os.path.exists(os.path.join(a.code, "pinphone.py")):
        print("no pinphone.py in --code %s" % a.code)
        return 2
    sys.path.insert(0, GOLDEN)
    import gl_common as C
    env = C.load_json(os.path.join(a.fixture, "env.json"))
    worlds = a.world or gl_worlds.ORDER
    for w in worlds:
        if w not in gl_worlds.WORLDS:
            print("unknown world %s (one of %s)" % (w, ", ".join(gl_worlds.ORDER)))
            return 2
    t0 = time.perf_counter()
    if a.jobs > 1 and len(worlds) > 1:
        # matplotlib's font cache is built once, by the first world alone, before the others start
        if not os.listdir(a.mpl):
            first = [run_world(worlds[0], a, env)]
            rest = worlds[1:]
        else:
            first, rest = [], worlds
        with ThreadPoolExecutor(a.jobs) as ex:
            res = dict(first + list(ex.map(lambda w: run_world(w, a, env), rest)))
    else:
        res = dict(run_world(w, a, env) for w in worlds)
    summary = {"fixture": a.fixture, "code": a.code, "worlds": res, "seconds": round(time.perf_counter() - t0, 1),
               "python": a.python, "jobs": a.jobs}
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    shutil.rmtree(a.work, ignore_errors=True) if not a.keep_work else None
    for w in worlds:
        r = res[w]
        print("%-18s rc %s  %6.1fs (+%.1fs copy)  %s cases  failed %d%s" % (
            w, r["rc"], r["seconds"], r["copy_seconds"], r["cases"], len(r["failed"] or []),
            ("  missing seams: %s" % r["missing_seams"]) if r.get("missing_seams") else ""))
    print("total %.1fs -> %s" % (summary["seconds"], a.out))
    return 0 if all(r["rc"] == 0 for r in res.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
