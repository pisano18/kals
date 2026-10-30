"""Golden SHADOW, part two (step 9 of the phone rebuild, lanes D7 / E / F): what is NOT one command module's own name.
Never imported by production code. shadow.py (the shared harness) compares Command.run against Phone.handle for a
module's declared names; this file compares the rest, by running the GOLDEN CASE SCRIPTS THEMSELVES (gl_cases.run_cmd,
run_pair, run_auth, run_tick, run_chart -- unchanged) twice in the same world: once on the old Phone, once on a stand-in
Phone whose entry points go to the new modules:

    handle(chat, text)       a minimal router over D7's modules: /pair first (phone.commands.pair), the paired-chat check,
                             the ledger refresh, then help_cmd / mute / controls / update, and ANYTHING ELSE ->
                             help_cmd.unknown_reply (unknown text, empty text, /nosuchcommand);
    alerts_tick()            phone.alerts.tick(Ctx.from_phone(phone), AlertState()) -- the alert state lives in a separate
                             AlertState (the scripts' reads / writes of last_state, seen_losses, last_daily ... go there);
    update_flag_tick()       phone.commands.update.flag_tick(Ctx.from_phone(phone));
    _chart_ctx(kind, tgc)    phone.chartq.chart_ctx(Ctx.from_phone(phone), kind, tgc) (every chart kind: PNG sha + caption).
Everything else is the real Phone's. Cases: the golden cmd/ cases whose command is D7's or unknown (plus EXTRA_TEXTS),
pair/*, auth/*, tick/* (alerts-state, -recorder, -disk, -loss, -daily, update-flag) and chart/*. A pair is identical when
the two result dicts are equal key by key (fence events as a sorted list, as shadow.py compares them).

    C:\\Python314\\python.exe research\\golden\\shadow_more.py --code C:\\kals-lane-4\\research [--only REGEX] [--world W]
                                                              [--jobs 2] [--no-charts]

Output as shadow.py's: <out>\\<world>\\shadow.json, <out>\\shadow.md, one line per world; exit 0 only when every pair is
identical in every world.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

GOLDEN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, GOLDEN)
import gl_common as C          # noqa: E402
import gl_worlds               # noqa: E402
import shadow as S             # noqa: E402

D7 = ("phone.commands.help_cmd", "phone.commands.pair", "phone.commands.mute", "phone.commands.controls",
      "phone.commands.update")
UNKNOWN = ("hello there", "/nosuchcommand", "")
EXTRA_TEXTS = ("what", "/HeLp@kalsbot", "  /mute  ", "/unmute@kalsbot", "/stop  yes ", "/stop@kalsbot yes", "/?@x",
               "/update@kalsbot", "/pause now", "/helpme", "?", "/ help")
ALERT_FIELDS = ("last_state", "last_rec", "seen_losses", "last_daily", "disk_level")


# ======================================================================================================== the child
class NewPhone:
    """The old Phone with its entry points routed to the new modules (see the module note)."""

    def __init__(self, ph, alerts_mod):
        object.__setattr__(self, "_ph", ph)
        object.__setattr__(self, "_st", alerts_mod.AlertState())

    def __getattr__(self, k):
        if k in ALERT_FIELDS:
            return getattr(self._st, k)
        return getattr(self._ph, k)

    def __setattr__(self, k, v):
        setattr(self._st if k in ALERT_FIELDS else self._ph, k, v)

    def _ctx(self, text="", chat_id=None):
        from phone.context import Ctx
        return Ctx.from_phone(self._ph, text, chat_id=chat_id)

    def handle(self, chat_id, text):
        import importlib
        from phone.context import split_command
        ph = self._ph
        _t, cmd, _a = split_command(text)
        if cmd == "/pair":
            return importlib.import_module("phone.commands.pair").COMMAND.run(self._ctx(text, chat_id))
        if ph.chat_id is None or chat_id != ph.chat_id:
            return None
        coms = {}
        for m in D7:
            for c in importlib.import_module("phone.command").of_module(m):
                for n in c.names:
                    coms[n] = c
        com = coms.get(cmd)
        if com is None or com.needs_ledger:
            ph.ledger.refresh()
        if com is None:
            return importlib.import_module("phone.commands.help_cmd").unknown_reply(self._ctx(text, chat_id))
        return com.run(self._ctx(text, chat_id))

    def alerts_tick(self):
        import importlib
        return importlib.import_module("phone.alerts").tick(self._ctx(), self._st)

    def update_flag_tick(self):
        import importlib
        return importlib.import_module("phone.commands.update").flag_tick(self._ctx())

    def _chart_ctx(self, kind, tgc):
        import importlib
        return importlib.import_module("phone.chartq").chart_ctx(self._ctx(), kind, tgc)


def new_runner(kind):
    def run(rt, arg):
        import importlib
        import gl_cases
        alerts_mod = importlib.import_module("phone.alerts")
        orig = gl_cases.make_phone

        def make(rt_, cfg=None, cfg_path=None):
            ph, tr = orig(rt_, cfg, cfg_path)
            return NewPhone(ph, alerts_mod), tr
        gl_cases.make_phone = make
        try:
            return {"cmd": gl_cases.run_cmd, "pair": gl_cases.run_pair, "auth": gl_cases.run_auth,
                    "tick": gl_cases.run_tick, "chart": gl_cases.run_chart}[kind](rt, arg)
        finally:
            gl_cases.make_phone = orig
    return run


def wanted_cases(rt, charts=True):
    import importlib
    import gl_cases
    from phone.context import split_command
    mine = set()
    for m in D7:
        for c in importlib.import_module("phone.command").of_module(m):
            mine.update(c.names)
    out, seen = [], set()
    for cid, kind, arg in gl_cases.case_list(rt) + [("cmd/" + t, "cmd", t) for t in EXTRA_TEXTS]:
        if cid in seen:
            continue
        if kind == "cmd":
            if not (split_command(arg)[1] in mine or arg in UNKNOWN or arg in EXTRA_TEXTS):
                continue
        elif kind == "chart" and not charts:
            continue
        elif kind not in ("cmd", "pair", "auth", "tick", "chart"):
            continue
        seen.add(cid)
        out.append((cid, kind, arg))
    return out


def _canon(k, v):
    if k == "fence":
        return sorted(C.canon(e) for e in (v or []))
    return C.canon(v)


def _png(out, res):
    """The chart case's PNG bytes (run_chart wrote them to <out>/charts/<name>), or None."""
    name = (res or {}).get("png")
    if not name:
        return None
    try:
        with open(os.path.join(out, "charts", name), "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _noise(a, b):
    """True when two PNGs are the same picture up to compare.py's render noise (NOISE_MAX levels on NOISE_PIXELS)."""
    if not a or not b:
        return False
    try:
        import io
        import compare
        from PIL import Image, ImageChops
        x, y = Image.open(io.BytesIO(a)).convert("RGBA"), Image.open(io.BytesIO(b)).convert("RGBA")
        if x.size != y.size:
            return False
        d = ImageChops.difference(x, y)
        if max(hi for _lo, hi in d.getextrema()) > compare.NOISE_MAX:
            return False
        return d.convert("RGB").convert("L").point(lambda v: 255 if v else 0).histogram()[255] <= compare.NOISE_PIXELS
    except Exception:                                           # noqa: BLE001
        return False


def child(a):
    import json
    with open(a.pairs, encoding="utf-8") as fh:              # read before the fence goes up
        spec = json.load(fh)
    import gl_child
    w = gl_child.open_world(a.fixture, a.code, a.world, a.work, a.out)
    if w is None:
        return 3
    import gl_cases
    for k in ("cmd", "pair", "auth", "tick", "chart"):
        gl_cases.EXTRA_RUNNERS["new-" + k] = new_runner(k)
    rt = w.rt
    load_errors = {}
    try:
        cases = wanted_cases(rt, charts=not spec.get("no_charts"))
    except Exception as e:                                      # noqa: BLE001
        cases = []
        load_errors["cases"] = S._err(e)
    rx = re.compile(spec["only"]) if spec.get("only") else None
    results = {}
    for cid, kind, arg in cases:
        if rx and not rx.search(cid):
            continue
        old, s_old, _tr_old = gl_cases.run_case(rt, (cid, kind, arg))
        png_old = _png(w.out, old) if kind == "chart" else None
        new, s_new, tr_new = gl_cases.run_case(rt, (cid, "new-" + kind, arg))
        keys = sorted(set(old) | set(new))
        diffs = {k: [old.get(k), new.get(k)] for k in keys if _canon(k, old.get(k)) != _canon(k, new.get(k))}
        status = "identical" if not diffs else "differs"
        if diffs and kind == "chart" and set(diffs) <= {"sha256", "bytes"} and _noise(png_old, _png(w.out, new)):
            status = "identical"             # compare.py's render-noise rule (the same picture, sub-pixel edges)
            diffs = {"noise": "PNG bytes differ by render noise only (compare.render_noise's limits)"}
        r = {"status": status, "diffs": diffs if status == "differs" else {}, "text": arg if kind == "cmd" else cid,
             "module": kind, "seconds": [round(s_old, 2), round(s_new, 2)]}
        if status == "identical" and diffs:
            r["noise"] = True
        if tr_new:
            r["new_trace"] = tr_new
        results[cid] = r
        print("shadow %-9s %5.2fs %5.2fs %s" % (r["status"], s_old, s_new, cid), flush=True)
    C.dump_json(os.path.join(w.out, "shadow.json"), {"world": a.world, "pairs": results, "load_errors": load_errors,
                                                    "missing_seams": rt.missing_seams}, codec=False)
    return 0


# ======================================================================================================== the driver
def run_world(world, a, env):
    """shadow.run_world, starting THIS file as the child."""
    import replay
    work = os.path.join(a.work, world)
    out = os.path.join(a.out, world)
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    replay.copy_fixture(a.fixture, work)
    gl_worlds.prepare(world, os.path.join(work, "repo", "results"), env)
    e = dict(os.environ)
    e.update(PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg", OPENBLAS_NUM_THREADS="1",
             MPLCONFIGDIR=os.path.join(work, "mpl"), TMP=os.path.join(work, "tmp"), TEMP=os.path.join(work, "tmp"),
             PYTHONIOENCODING="utf-8")
    for k in ("PYTHONPATH", "PYTHONSTARTUP", "PYTHONUTF8", "KALSHI_KEY_FILE"):
        e.pop(k, None)
    cmd = [a.python, "-u", os.path.abspath(__file__), "--child", "--fixture", a.fixture, "--code", a.code,
           "--world", world, "--work", work, "--out", out, "--pairs", a.pairs]
    t0 = time.perf_counter()
    with open(os.path.join(out, "stdout.txt"), "w", encoding="utf-8") as fh:
        rc = subprocess.run(cmd, cwd=work, env=e, stdout=fh, stderr=subprocess.STDOUT, timeout=a.timeout).returncode
    secs = time.perf_counter() - t0
    if not a.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    try:
        res = C.load_json(os.path.join(out, "shadow.json"), codec=False)
    except (OSError, ValueError):
        res = None
    return world, {"rc": rc, "seconds": round(secs, 1), "res": res}


def main():
    ap = argparse.ArgumentParser(description="golden shadow part two: D7 routing, alerts, update flag, chart contexts")
    ap.add_argument("--only", default=None, help="regex over case ids ('tick/alerts-disk', 'cmd/hello there')")
    ap.add_argument("--world", action="append", help="repeatable; default every world")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--code", default=os.path.dirname(GOLDEN), help="the research folder of the tree under test")
    ap.add_argument("--fixture", default=None, help="default: the newest in %s" % S.FIXTURES)
    ap.add_argument("--out", default=None, help="default %s\\<stamp>-more" % S.SHADOW_ROOT)
    ap.add_argument("--work", default=None)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--lines", type=int, default=60)
    ap.add_argument("--no-charts", action="store_true", help="skip the chart/* cases (the slowest)")
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--pairs", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.child:
        a.world = a.world[-1]
        return child(a)
    a.code = os.path.abspath(a.code)
    a.fixture = os.path.abspath(a.fixture or S.newest_fixture() or "")
    if not os.path.isfile(os.path.join(a.fixture, "manifest.json")):
        print("no fixture (--fixture, or one under %s)" % S.FIXTURES)
        return 2
    for m in D7 + ("phone.alerts", "phone.chartq"):
        if not os.path.exists(os.path.join(a.code, *m.split(".")) + ".py"):
            print("no module %s in --code %s" % (m, a.code))
            return 2
    worlds = a.world or gl_worlds.ORDER
    for w in worlds:
        if w not in gl_worlds.WORLDS:
            print("unknown world %s (one of %s)" % (w, ", ".join(gl_worlds.ORDER)))
            return 2
    stamp = time.strftime("%Y%m%dT%H%M%S") + "-%d-more" % os.getpid()
    a.out = os.path.abspath(a.out or os.path.join(S.SHADOW_ROOT, stamp))
    a.work = os.path.abspath(a.work or os.path.join(a.out, "_work"))
    os.makedirs(a.out, exist_ok=True)
    a.pairs = os.path.join(a.out, "pairs.json")
    import json
    with open(a.pairs, "w", encoding="utf-8") as fh:
        json.dump({"only": a.only, "no_charts": a.no_charts}, fh, indent=1)
    env = C.load_json(os.path.join(a.fixture, "env.json"))
    t0 = time.perf_counter()
    print("shadow_more: D7 routing + alerts + update flag%s -> %d world(s), code %s"
          % ("" if a.no_charts else " + chart contexts", len(worlds), a.code), flush=True)
    with ThreadPoolExecutor(max(1, a.jobs)) as ex:
        res = dict(ex.map(lambda w: run_world(w, a, env), worlds))
    if not a.keep_work:
        shutil.rmtree(a.work, ignore_errors=True)
    bad, total = S.report(a, res, worlds)
    verdict = ("IDENTICAL in all %d world(s) (%d pair results)" % (len(worlds), total) if not bad
               else "DIFFERENT or failed in %d of %d world(s) -- see %s" % (bad, len(worlds), os.path.join(a.out, "shadow.md")))
    print("shadow_more: %s  %.1fs -> %s" % (verdict, time.perf_counter() - t0, a.out))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
