"""Golden SHADOW (step 9 of the phone rebuild): the OLD Phone path against a NEW command module, byte for byte, in
every golden world. Never imported by production code.

    python research\\golden\\shadow.py --module phone.commands.hedges [--module ...] [--case "/server help=phone.commands.server"]
                                      [--only REGEX] [--world W ...] [--jobs 2] [--code <research dir>] [--fixture DIR]
                                      [--out DIR] [--keep-work]

What is compared, for every message text of every module (each name the module's Command(s) declare, plus its
`examples`), in each world (default all 8):
  OLD  Phone.handle(chat, text) -- exactly golden replay's cmd case (gl_cases.run_cmd): the if-chain, the old text_*;
  NEW  what the router will do (step 10): split the text as Phone.handle does, refresh the Ledger (needs_ledger), the
       hidden-bot check (a paused / retired bot's command: the router answers, not the module -> the pair is 'hidden',
       not compared), then Command.run(Ctx.from_phone(phone, text)).
Fields: the reply text, its type (Html / str / None), the exact split_html / split_text chunks, everything say() sent
(worker messages), the mute state, an exception, the chart kind (old tgcharts.kind_of(cmd) vs the Command's
kind_of(cmd)), the Kalshi requests made (as a set), the fence's events, the case status. Both sides run in the SAME
world process through gl_cases.run_case (caches reset, health / clock / scratch files put back before each), so the only
difference is the code path.

A world is built exactly as replay.py builds it (copy_fixture + gl_worlds.prepare, then gl_child.open_world: the same
fixture, frozen clock, fence, seams and guards). The harness always runs from THIS file's folder; --code is the tree
under test (default: this tree's research folder), so an agent in its own worktree runs its own copy:

    C:\\Python314\\python.exe C:\\kals-lane-D6\\research\\golden\\shadow.py --code C:\\kals-lane-D6\\research --module phone.commands.hedges

--case takes a golden case id or a message text, '=' and the module: "cmd//server help=phone.commands.server",
"/stop yes=phone.commands.controls". No --module / --case: every module in <code>\\phone\\commands. --only filters the
pair ids ('hedges /hedges') by regex. Output: <out>\\<world>\\shadow.json, <out>\\shadow.md (every difference with a
unified diff), one line per world on stdout. Exit 0 only when every compared pair is identical in every world run.
"""
import argparse
import difflib
import json
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

FIXTURES = r"C:\kals-golden\fixtures"
SHADOW_ROOT = r"C:\kals-golden\shadow"
# compared fields of a case result (gl_cases.run_case adds the last ones); 'fence' is compared as a sorted list
FIELDS = ("type", "reply", "chunks", "chunks_error", "sent", "muted", "raised", "chart_kind", "kalshi_asked",
          "kalshi_unrecorded", "status", "fail_why", "threads_left", "standins_read", "fence")


# ======================================================================================================== the child
def _err(e):
    return "%s: %s" % (type(e).__name__, str(e)[:400])


def text_of(spec):
    """A golden case id ('cmd//server help') or a message text ('/server help') -> the message text."""
    return spec[4:] if spec.startswith("cmd/") else spec


def run_shadow(rt, arg):
    """gl_cases runner 'shadow': the NEW path for one message (see the module note)."""
    import importlib
    import gl_cases
    import gl_fence
    text, module = arg
    pp = rt.mods["pinphone"]
    ctxmod = importlib.import_module("phone.context")
    cmdmod = importlib.import_module("phone.command")
    ph, tr = gl_cases.make_phone(rt)
    out = {"input": text, "chat": C.CHAT}
    _t, cmd, _a = ctxmod.split_command(text)
    reply, com = None, None
    try:
        com = next((c for c in cmdmod.of_module(module) if cmd in c.names), None)
        if com is None:
            raise LookupError("%s declares no command %r" % (module, cmd))
        if com.needs_ledger:
            ph.ledger.refresh()                 # Phone.handle refreshes before every command (the router will too)
        ctx = ctxmod.Ctx.from_phone(ph, text, chat_id=C.CHAT)
        bot = importlib.import_module("bots").by_command(cmd)
        if bot is not None and bot.name not in ctx.active():
            out["hidden"] = bot.name            # the router's answer (text_hidden), not the module's
        else:
            reply = com.run(ctx)
    except Exception as e:                                      # noqa: BLE001
        reply = None
        out["raised"] = _err(e)
    gl_fence.join_threads(rt.fence, 120)
    out.update(gl_cases.reply_view(pp, reply))
    out["sent"] = list(tr.sent)
    out["muted"] = getattr(ph, "muted", None)
    try:
        out["chart_kind"] = com.kind_of(cmd) if com is not None else None
    except Exception as e:                                      # noqa: BLE001
        out["chart_kind"] = _err(e)
    return out


def view(res):
    v = {k: res.get(k) for k in FIELDS if k != "fence"}
    v["fence"] = sorted(C.canon(e) for e in (res.get("fence") or []))
    return v


def child(a):
    with open(a.pairs, encoding="utf-8") as fh:              # read before the fence goes up
        spec = json.load(fh)
    import gl_child
    w = gl_child.open_world(a.fixture, a.code, a.world, a.work, a.out)
    if w is None:
        return 3
    import gl_cases
    gl_cases.EXTRA_RUNNERS["shadow"] = run_shadow
    rt = w.rt
    import importlib
    cmdmod = importlib.import_module("phone.command")
    pairs, load_errors = [], {}
    for module in spec["modules"]:
        try:
            for com in cmdmod.of_module(module):
                for t in tuple(com.names) + tuple(com.examples):
                    pairs.append((t, module))
        except Exception as e:                                  # noqa: BLE001
            load_errors[module] = _err(e)
    pairs += [(text_of(t), m) for t, m in spec["cases"]]
    seen, todo = set(), []
    rx = re.compile(spec["only"]) if spec.get("only") else None
    for t, m in pairs:
        pid = "%s %s" % (m.rpartition(".")[2], t)
        if pid in seen or (rx and not rx.search(pid)):
            continue
        seen.add(pid)
        todo.append((pid, t, m))
    results = {}
    for pid, t, m in todo:
        old, s_old, tr_old = gl_cases.run_case(rt, ("shadow-old/" + t, "cmd", t))
        new, s_new, tr_new = gl_cases.run_case(rt, ("shadow-new/" + t, "shadow", (t, m)))
        if new.get("hidden"):
            r = {"status": "hidden", "bot": new["hidden"]}
        else:
            vo, vn = view(old), view(new)
            diffs = {k: [vo[k], vn[k]] for k in vo if C.canon(vo[k]) != C.canon(vn[k])}
            r = {"status": "identical" if not diffs else "differs", "diffs": diffs}
            if tr_new:
                r["new_trace"] = tr_new
        r.update(text=t, module=m, seconds=[round(s_old, 2), round(s_new, 2)])
        results[pid] = r
        print("shadow %-9s %5.2fs %5.2fs %s" % (r["status"], s_old, s_new, pid), flush=True)
    C.dump_json(os.path.join(w.out, "shadow.json"), {"world": a.world, "pairs": results, "load_errors": load_errors,
                                                    "missing_seams": rt.missing_seams}, codec=False)
    return 0


# ======================================================================================================== the driver
def run_world(world, a, env):
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


def _lines(x):
    if isinstance(x, str):
        return x.splitlines()
    return json.dumps(x, indent=1, ensure_ascii=False, sort_keys=True).splitlines()


def report(a, res, worlds):
    md = ["# Golden shadow: old Phone path vs new command modules", "",
          "code `%s`, fixture `%s`, %s" % (a.code, os.path.basename(a.fixture), time.strftime("%Y-%m-%d %H:%M:%S")), "",
          "| world | identical | differs | hidden | rc |", "|---|---|---|---|---|"]
    bad = 0
    total = 0
    per = []
    for w in worlds:
        r = res[w]
        pr = ((r["res"] or {}).get("pairs") or {})
        n = {k: sum(1 for x in pr.values() if x["status"] == k) for k in ("identical", "differs", "hidden")}
        le = (r["res"] or {}).get("load_errors") or {}
        ok = r["rc"] == 0 and r["res"] is not None and not n["differs"] and not le and pr
        bad += 0 if ok else 1
        total += n["identical"]
        md.append("| %s | %d | %d | %d | %s |" % (w, n["identical"], n["differs"], n["hidden"], r["rc"]))
        per.append((w, r, pr, n, le, ok))
        print("%-18s %s  identical %3d  differs %3d  hidden %3d  %5.1fs%s%s" % (
            w, "ok  " if ok else "FAIL", n["identical"], n["differs"], n["hidden"], r["seconds"],
            ("  rc %s (see %s)" % (r["rc"], os.path.join(a.out, w, "stdout.txt"))) if r["rc"] else "",
            ("  load errors: %s" % le) if le else ""))
    for w, r, pr, n, le, ok in per:
        for pid, x in sorted(pr.items()):
            if x["status"] != "differs":
                continue
            md += ["", "## %s / %s" % (w, pid)]
            for k, (o, nw) in sorted(x["diffs"].items()):
                md += ["", "`%s`:" % k, "```diff"]
                md += list(difflib.unified_diff(_lines(o), _lines(nw), "old", "new", lineterm="", n=2))[:a.lines]
                md.append("```")
            if x.get("new_trace"):
                md += ["", "new path traceback:", "```", x["new_trace"], "```"]
    with open(os.path.join(a.out, "shadow.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    return bad, total


def newest_fixture():
    try:
        ds = sorted(d for d in os.listdir(FIXTURES) if os.path.isfile(os.path.join(FIXTURES, d, "manifest.json")))
    except OSError:
        ds = []
    return os.path.join(FIXTURES, ds[-1]) if ds else None


def main():
    ap = argparse.ArgumentParser(description="golden shadow: old Phone path vs new command modules, every world")
    ap.add_argument("--module", action="append", default=[], help="phone.commands.<x> (repeatable)")
    ap.add_argument("--case", action="append", default=[], help='"TEXT=MODULE": a message text or cmd/ case id')
    ap.add_argument("--only", default=None, help="regex over pair ids ('hedges /hedges')")
    ap.add_argument("--world", action="append", help="repeatable; default every world")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--code", default=os.path.dirname(GOLDEN), help="the research folder of the tree under test")
    ap.add_argument("--fixture", default=None, help="default: the newest in %s" % FIXTURES)
    ap.add_argument("--out", default=None, help="default %s\\<stamp>" % SHADOW_ROOT)
    ap.add_argument("--work", default=None, help="scratch folder (default <out>\\_work)")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--lines", type=int, default=60, help="diff lines per field in shadow.md")
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--pairs", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.child:
        a.world = a.world[-1]
        return child(a)
    a.code = os.path.abspath(a.code)
    a.fixture = os.path.abspath(a.fixture or newest_fixture() or "")
    if not os.path.isfile(os.path.join(a.fixture, "manifest.json")):
        print("no fixture (--fixture, or one under %s)" % FIXTURES)
        return 2
    if not os.path.exists(os.path.join(a.code, "pinphone.py")):
        print("no pinphone.py in --code %s" % a.code)
        return 2
    cases = []
    for c in a.case:
        t, sep, m = c.rpartition("=")
        if not sep or not m.strip():
            print("--case wants TEXT=MODULE: %r" % c)
            return 2
        cases.append((t, m.strip()))
    modules = list(a.module)
    if not modules and not cases:
        d = os.path.join(a.code, "phone", "commands")
        modules = sorted("phone.commands." + (f[:-3] if f.endswith(".py") else f) for f in os.listdir(d)
                         if not f.startswith("_") and f != "tests" and (f.endswith(".py") or
                                                       os.path.isfile(os.path.join(d, f, "__init__.py")))) \
            if os.path.isdir(d) else []
    for m in modules + [m for _t, m in cases]:
        p = os.path.join(a.code, *m.split("."))
        if m.startswith("phone.commands.") and not (os.path.exists(p + ".py")
                                                   or os.path.isfile(os.path.join(p, "__init__.py"))):
            print("no module %s in --code %s" % (m, a.code))
            return 2
    if not modules and not cases:
        print("nothing to shadow: no module in %s" % os.path.join(a.code, "phone", "commands"))
        return 2
    worlds = a.world or gl_worlds.ORDER
    for w in worlds:
        if w not in gl_worlds.WORLDS:
            print("unknown world %s (one of %s)" % (w, ", ".join(gl_worlds.ORDER)))
            return 2
    stamp = time.strftime("%Y%m%dT%H%M%S") + "-%d" % os.getpid()
    a.out = os.path.abspath(a.out or os.path.join(SHADOW_ROOT, stamp))
    a.work = os.path.abspath(a.work or os.path.join(a.out, "_work"))
    os.makedirs(a.out, exist_ok=True)
    a.pairs = os.path.join(a.out, "pairs.json")
    with open(a.pairs, "w", encoding="utf-8") as fh:
        json.dump({"modules": modules, "cases": cases, "only": a.only}, fh, indent=1)
    env = C.load_json(os.path.join(a.fixture, "env.json"))
    t0 = time.perf_counter()
    print("shadow: %s%s -> %d world(s), code %s" % (", ".join(modules), (" + %d case(s)" % len(cases)) if cases else "",
                                                    len(worlds), a.code), flush=True)
    with ThreadPoolExecutor(max(1, a.jobs)) as ex:
        res = dict(ex.map(lambda w: run_world(w, a, env), worlds))
    if not a.keep_work:
        shutil.rmtree(a.work, ignore_errors=True)
    bad, total = report(a, res, worlds)
    verdict = ("IDENTICAL in all %d world(s) (%d pair results)" % (len(worlds), total) if not bad
               else "DIFFERENT or failed in %d of %d world(s) -- see %s" % (bad, len(worlds), os.path.join(a.out, "shadow.md")))
    print("shadow: %s  %.1fs -> %s" % (verdict, time.perf_counter() - t0, a.out))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
