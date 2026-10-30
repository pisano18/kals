"""The golden cases: every phone command and alias, pairing, every chart kind, alert scripts and the botstats data
views. Shared by capture.py (trace pass, on the server) and gl_child.py (replay). Never imported by production code.

Each case returns a plain dict; the runner adds what the fence saw (Kalshi requests, refused reads / writes /
network / processes) and a status. Nothing here knows a bot name the code under test does not tell it, except the
fixed command list from DESIGN 1.1 (so a command that disappears shows as a changed case, not a missing one).
"""
import copy
import inspect
import os
import re
import shutil
import sys
import time
import traceback
from collections import namedtuple

import gl_common as C
import gl_fence

# DESIGN 1.1: every command and alias, plus the arguments that change a reply
BASE_CMDS = [
    "/status", "/s", "/status@kalsbot", "/start@", "/today", "/yesterday", "/days", "/open", "/fills", "/bets",
    "/brief", "/summary", "/market", "/losses", "/hedges", "/stats", "/race", "/racestats", "/bots", "/pin",
    "/forecaster", "/fc", "/ladder", "/weather", "/wx", "/fx", "/jb", "/jumpband", "/bars", "/funds", "/bank",
    "/accounts", "/speed", "/server", "/server help", "/server ?", "/server aws", "/server setup", "/features",
    "/pause", "/start", "/start@kalsbot", "/stop", "/stop yes", "/stop no", "/mute", "/unmute", "/update", "/help",
    "/?", "/HELP", "hello there", "/nosuchcommand", "",
]
TICKS = ["alerts-state", "alerts-recorder", "alerts-disk", "alerts-loss", "alerts-daily", "update-flag"]
try:                    # v-tg-rebuild step 12 (lane Q): the monitor's alert scripts, in their own file
    import gl_ticks_q as _TQ
    TICKS += list(_TQ.TICKS)
except ImportError:
    _TQ = None
DATA = ["all_bots", "active_bots", "owner", "version_of", "kind_of", "tables"]
SYNTH_TICKERS = [  # owner() on tickers of every family, in every sub (the fixture's own tickers are added)
    "KXBTC15M-26OCT301300-00", "KXETH15M-26OCT301300-00", "KXBNB15M-26OCT301300-00", "KXHYPE15M-26OCT301300-00",
    "KXZEC15M-26OCT301300-00", "KXNEAR15M-26OCT301300-00", "KXCRYPTOLEAD15M-26OCT301300", "KXCRYPTOLEADX-26OCT30",
    "KXBTCD-26OCT3013-T100000", "KXDOGED-26OCT3013-T0.2", "KXEURUSD15M-26OCT301300-T1.08", "KXUSDJPY15M-26OCT301300-T150",
    "KXGOLD15M-26OCT301300-T2600", "KXHIGHNY-26OCT30-T60", "KXRAINNYC-26OCT30", "KXNFLGAME-26NOV01NYGDAL-DAL", ""]


# ======================================================================================================== Kalshi
class KalshiStore:
    """Replay: answers recorded GETs by (path, sorted params); an unrecorded one is answered 599 and FAILS the case.
    mode 'down': every GET is answered 500 (the kalshi-down world)."""

    def __init__(self, calls, mode="record"):
        self.calls = calls
        self.mode = mode
        self.asked, self.unrecorded = [], []

    def get(self, path, params=None, auth=True):
        key = C.kalshi_key(path, params)
        self.asked.append(key)
        if self.mode == "down":
            return 500, {"error": {"code": "internal_server_error", "message": "golden world: Kalshi is down"}}
        if key in self.calls:
            st, body = self.calls[key]
            return st, copy.deepcopy(body)
        self.unrecorded.append(key)
        return 599, "golden: this request was not recorded at capture: %s" % key


class KalshiRecorder:
    """Capture: the REAL kauth.get (GET only by construction), each distinct request asked of Kalshi once; a 429 is
    not kept (botstats' getter retries it)."""

    CAP = 250                                           # a runaway pager stops here

    def __init__(self, real_get, fence):
        self.real_get, self.fence = real_get, fence
        self.calls = {}
        self.asked, self.unrecorded = [], []
        self.real_requests = 0

    def get(self, path, params=None, auth=True):
        key = C.kalshi_key(path, params)
        self.asked.append(key)
        if key in self.calls:
            st, body = self.calls[key]
            return st, copy.deepcopy(body)
        if self.real_requests >= self.CAP:
            return -1, "golden capture: over %d real Kalshi requests, refused" % self.CAP
        self.real_requests += 1
        with self.fence.allow_net():
            st, body = self.real_get(path, params, auth)
        if st == 429:                                   # the getter retries at once (sleep is frozen): wait for real
            gl_fence.ORIG.get("time.sleep", time.sleep)(1.0)
        else:
            self.calls[key] = (st, copy.deepcopy(body))
        return st, body


def fake_kauth(store):
    import types
    m = types.ModuleType("kauth")
    m.__file__ = "<golden fake kauth>"
    m.KEY_ID = "golden-no-key"
    m.BASE = "https://golden.invalid"
    m.PREFIX = "/trade-api/v2"

    def headers(method, path):
        raise gl_fence.FenceError("golden: no Kalshi key here")
    m.headers = headers
    m.get = store.get
    return m


# ======================================================================================================== runtime
class FakeTransport:
    def __init__(self):
        self.sent, self.photos = [], []

    def send(self, chat_id, text):
        self.sent.append({"chat": chat_id, "type": tname(text), "text": str(text)})

    def send_photo(self, chat_id, png, caption=None):
        self.photos.append({"chat": chat_id, "sha256": C.sha(png), "caption": caption})

    def get_updates(self, offset, timeout=25):
        return []


def tname(x):
    if x is None:
        return "None"
    return "Html" if getattr(x, "is_html", False) else type(x).__name__


class Runtime:
    """What every case reads instead of the machine: the frozen clock, the recorded health / process table /
    machine / ping / disk, and the Kalshi store."""

    def __init__(self, fence, clock, env, health, procs, kalshi, mode, out_dir, norm, cfg_path):
        self.fence, self.clock, self.env = fence, clock, env
        self.health0 = health
        self.health = copy.deepcopy(health)
        self.procs = procs                       # [[pid, started, cmdline]] every python.exe, or None (unreadable)
        self.kalshi = kalshi
        self.mode = mode
        self.out_dir = out_dir
        self.norm = norm
        self.cfg_path = cfg_path
        self.mods = {}
        self.ledger = None
        self.missing_seams = []
        self.cache_reset = []

    # process tables in each reader's shape
    def pp_rows(self):
        return None if self.procs is None else [(int(p), str(cl)) for p, _s, cl in self.procs]

    def bs_rows_all(self):
        return None if self.procs is None else [[int(p), str(s), str(cl)] for p, s, cl in self.procs]

    def bs_native(self):
        bs = self.mods.get("botstats")
        rows = self.bs_rows_all()
        if rows is None or bs is None:
            return rows
        try:
            return [r for r in rows if any(bs.SPEC[b]["script"] in r[2] for b in bs.BOTS)]
        except Exception:                                       # noqa: BLE001
            return rows

    def bs_procs_arg(self):
        """What Phone.bs_procs / all_bots(procs=) get: the table, or a reader that fails."""
        if self.procs is None:
            return lambda: None
        return self.bs_native()


def apply_seams(rt):
    """Point the code's machine readers at the recorded values. A seam the tree no longer has is listed (meta.json)."""
    pp, bs, pd = rt.mods.get("pinphone"), rt.mods.get("botstats"), rt.mods.get("pindesk")
    # v-tg-rebuild step 11: pinphone.py is a launcher; the helpers the commands read (ctx.pp) live in phone.shared, and
    # the AWS reader in phone.commands.server.aws (step 9). Seams go where the code looks them up; an older tree has
    # neither module and keeps every seam on pinphone itself.
    ppm = sys.modules.get("phone.shared") or pp
    aws = sys.modules.get("phone.commands.server.aws")

    def put(mod, name, fn):
        if mod is None or not hasattr(mod, name):
            rt.missing_seams.append("%s.%s" % (getattr(mod, "__name__", "?"), name))
            return
        setattr(mod, name, fn)
    put(ppm, "list_python_procs", lambda timeout=30: rt.pp_rows())
    put(bs, "_procs_native", lambda: rt.bs_native())
    put(bs, "read_procs", lambda timeout=40: rt.bs_native())
    # botdata.procs (v-tg-rebuild step 4): the ONE process table. Every reader of every python.exe -> the recorded table
    # ([pid, started, command line], None when unreadable), so procs.table() / cached() / refresh_once() and the
    # refresher never read this machine's real processes. Only when the tree has the module (the B0 tree has not).
    bp = sys.modules.get("botdata.procs")
    if bp is not None:
        for name, fn in (("native_rows", lambda: rt.bs_rows_all()), ("wmi_rows", lambda timeout=40: rt.bs_rows_all()),
                         ("read_all", lambda timeout=40: rt.bs_rows_all())):
            put(bp, name, fn)
    put(ppm, "machine_read", lambda sample_s=0.5: copy.deepcopy(rt.env.get("machine")))
    put(ppm, "kalshi_ping", lambda max_age_s=60: copy.deepcopy(rt.env.get("ping")))
    put(ppm, "_aws_http", _refuse_aws)
    if aws is not None:
        put(aws, "_aws_http", _refuse_aws)
    put(pd, "health", lambda ledger=None: copy.deepcopy(rt.health))

    def stub(name):
        def do(log=None, *a, **k):
            rt.fence.event("control_stubbed", name)
            if callable(log):
                log("golden stub: pindesk.%s was not run" % name)
        return do
    for name in ("do_start", "do_pause", "do_stop"):              # NEVER the real controls, in capture or replay
        put(pd, name, stub(name))
    du = rt.env.get("disk_usage")
    if du:
        U = namedtuple("usage", "total used free")
        shutil.disk_usage = lambda path: U(*du)


def _refuse_aws(method, url, headers=None, body=None, timeout=None):
    raise gl_fence.FenceError("golden: no AWS here (the capture records the not-connected path)")


def snapshot_caches(rt):
    """Every module-level dict / list / set whose name starts with '_' in the code under test (the unowned caches:
    _RAW, _LOGS, _MEMO, _ACTIVE, _PROCS ...), as it is right after import; restore_caches puts them back before
    every case so no case depends on the one before it."""
    code = os.path.normcase(rt.env["_code"])
    snap = []
    for name, m in sorted(sys.modules.items()):
        f = getattr(m, "__file__", None)
        if not f or not os.path.normcase(os.path.abspath(f)).startswith(code + os.sep):
            continue
        for k, v in list(vars(m).items()):
            if k.startswith("_") and not k.startswith("__") and type(v) in (dict, list, set):
                try:
                    snap.append((m, k, v, copy.deepcopy(v)))
                except Exception:                               # noqa: BLE001
                    pass
    rt.cache_reset = snap


def restore_caches(rt):
    for m, k, obj, saved in rt.cache_reset:
        cur = getattr(m, k, None)
        if cur is not obj:
            setattr(m, k, obj)
        v = copy.deepcopy(saved)
        obj.clear()
        if isinstance(obj, dict):
            obj.update(v)
        elif isinstance(obj, list):
            obj.extend(v)
        else:
            obj.update(v)


# ======================================================================================================== phones
def make_phone(rt, cfg=None, cfg_path=None):
    pp = rt.mods["pinphone"]
    cfg = dict(cfg if cfg is not None else {"chat_id": C.CHAT, "secret": C.SECRET, "token": C.TOKEN})
    state = rt

    def health_fn():
        return copy.deepcopy(state.health)
    want = {"ledger": rt.ledger, "health_fn": health_fn, "cfg_path": cfg_path or rt.cfg_path,
            "now_fn": lambda: rt.clock.T, "procs_fn": lambda: rt.pp_rows()}
    try:
        sig = inspect.signature(pp.Phone.__init__).parameters
        kw = {k: v for k, v in want.items() if k in sig}
    except (TypeError, ValueError):
        kw = want
    tr = FakeTransport()
    ph = pp.Phone(cfg, tr, **kw)
    for attr, val in (("bs_procs", rt.bs_procs_arg()), ("bs_getter", None), ("funds_getter", None),
                      ("machine_fn", lambda: copy.deepcopy(rt.env.get("machine"))),
                      ("ping_fn", lambda: copy.deepcopy(rt.env.get("ping"))), ("aws_http", _refuse_aws),
                      ("charts_on", False)):
        if hasattr(ph, attr):
            setattr(ph, attr, val)
    return ph, tr


def reply_view(pp, reply):
    out = {"type": tname(reply), "reply": None if reply is None else str(reply), "chunks": []}
    if reply is None:
        return out
    try:
        if getattr(reply, "is_html", False):
            out["chunks"] = [str(x) for x in pp.split_html(reply)]
        else:
            out["chunks"] = [str(x) for x in pp.split_text(str(reply))]
    except Exception as e:                                      # noqa: BLE001
        out["chunks_error"] = "%s: %s" % (type(e).__name__, e)
    return out


def _err(e):
    return "%s: %s" % (type(e).__name__, str(e)[:400])


# ======================================================================================================== the case list
def case_list(rt):
    pp, tgc = rt.mods["pinphone"], rt.mods.get("tgcharts")
    cmds = list(BASE_CMDS)
    extra = set()
    for d in (getattr(pp, "BOT_CMDS", {}), getattr(tgc, "CMD_KIND", {}) if tgc else {}):
        extra.update(k for k in d if isinstance(k, str))
    try:
        h = pp.help_text() if hasattr(pp, "help_text") else pp.HELP_TEXT
        extra.update(re.findall(r"(?<![\w/<])(/[a-z][a-z0-9_]*)", str(h)))
    except Exception:                                           # noqa: BLE001
        pass
    cmds += sorted(x for x in extra if x not in cmds)
    cases = [("cmd/" + c, "cmd", c) for c in cmds]
    cases += [("pair/right", "pair", "/pair " + C.SECRET), ("pair/right-at", "pair", "/pair@kalsbot " + C.SECRET),
              ("pair/wrong", "pair", "/pair not-the-secret"), ("pair/empty", "pair", "/pair"),
              ("auth/other-chat", "auth", "other"), ("auth/unpaired", "auth", "unpaired")]
    kinds = sorted(set(getattr(tgc, "CMD_KIND", {}).values())) if tgc else []
    cases += [("chart/" + k, "chart", k) for k in kinds]
    cases += [("tick/" + t, "tick", t) for t in TICKS]
    cases += [("data/" + d, "data", d) for d in DATA]
    return cases


# ======================================================================================================== runners
EXTRA_RUNNERS = {}      # kind -> runner(rt, arg): shadow.py adds its 'shadow' kind; replay's case list never uses one


def run_case(rt, case):
    cid, kind, arg = case
    restore_caches(rt)
    rt.health = copy.deepcopy(rt.health0)
    rt.fence.take_events()
    gl_fence.join_threads(rt.fence, 0)
    rt.fence.case = cid
    rt.kalshi.asked, rt.kalshi.unrecorded = [], []
    rt.clock.slept = 0.0
    T0 = rt.clock.T
    t0 = time.perf_counter()
    try:
        res = ({"cmd": run_cmd, "pair": run_pair, "auth": run_auth, "chart": run_chart, "tick": run_tick,
                "data": run_data}.get(kind) or EXTRA_RUNNERS[kind])(rt, arg)
    except Exception as e:                                      # noqa: BLE001
        res = {"harness_error": _err(e), "trace": traceback.format_exc()[-1500:]}
    left = gl_fence.join_threads(rt.fence, 120)
    rt.clock.T = T0
    if rt.fence.track_root:          # botstats' cache save, /pair's config, the update flag ...: put back for the next case
        rt.fence.restore_writes()
    ev = rt.fence.take_events()
    st = sorted({os.path.basename(e["detail"]) for e in ev if e["kind"] == "standin_read"})
    ev = [e for e in ev if e["kind"] != "standin_read"]
    if st:   # data the fixture holds only as a 0-byte stand-in was read (old paper-arm logs: /brief, /bars)
        paper = [n for n in st if n.lower().startswith("pinrun-paper-")]
        res["standins_read"] = {"paper_arm_logs": len(paper), "others": [n for n in st if n not in paper]}
    res["case"] = cid
    res["fence"] = ev
    # which Kalshi requests, as a set: a refactor that drops a duplicate read or reorders them changes nothing here
    res["kalshi_asked"] = sorted(set(rt.kalshi.asked))
    res["kalshi_unrecorded"] = sorted(set(rt.kalshi.unrecorded))
    if left:
        res["threads_left"] = left
    # a refused process (bars' watcher scripts) is shown in "fence" but is not a failure: nothing ever runs here
    bad = [e["kind"] for e in ev if e["kind"] in ("read_denied", "write_denied", "network_refused", "kill_refused")]
    res["status"] = "FAIL" if (bad or rt.kalshi.unrecorded or left or "harness_error" in res) else "ok"
    if res["status"] == "FAIL":
        res["fail_why"] = sorted(set(bad + (["kalshi_unrecorded"] if rt.kalshi.unrecorded else []) +
                                     (["threads_left"] if left else []) +
                                     (["harness_error"] if "harness_error" in res else [])))
    secs = time.perf_counter() - t0
    trace = res.pop("trace", None)
    return rt.norm.deep(res), secs, trace


def run_cmd(rt, text, chat=C.CHAT, ph=None):
    pp = rt.mods["pinphone"]
    if ph is None:
        ph, tr = make_phone(rt)
    else:
        tr = ph.tg
    out = {"input": text, "chat": chat}
    try:
        reply = ph.handle(chat, text)
    except Exception as e:                                      # noqa: BLE001
        reply = None
        out["raised"] = _err(e)
    gl_fence.join_threads(rt.fence, 120)
    out.update(reply_view(pp, reply))
    out["sent"] = list(tr.sent)
    out["muted"] = getattr(ph, "muted", None)
    cmd = (text or "").strip().partition(" ")[0].lower().split("@")[0]
    tgc = rt.mods.get("tgcharts")
    try:
        out["chart_kind"] = tgc.kind_of(cmd) if tgc else None
    except Exception as e:                                      # noqa: BLE001
        out["chart_kind"] = _err(e)
    return out


def run_pair(rt, text):
    path = rt.cfg_path
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
    ph, tr = make_phone(rt, cfg={"chat_id": None, "secret": C.SECRET, "token": C.TOKEN}, cfg_path=path)
    out = run_cmd(rt, text, chat=C.CHAT, ph=ph)
    out["paired_chat"] = ph.cfg.get("chat_id")
    try:
        with open(path, encoding="utf-8") as fh:
            out["saved_cfg"] = fh.read()
    except OSError as e:
        out["saved_cfg"] = None if isinstance(e, FileNotFoundError) else _err(e)
    if out["paired_chat"] == C.CHAT:                            # the paired chat is answered from now on
        out["after"] = run_cmd(rt, "/help", chat=C.CHAT, ph=ph)["type"]
    return out


def run_auth(rt, which):
    if which == "other":
        return run_cmd(rt, "/status", chat=C.OTHER_CHAT)
    ph, tr = make_phone(rt, cfg={"chat_id": None, "secret": C.SECRET, "token": C.TOKEN})
    return run_cmd(rt, "/status", chat=C.CHAT, ph=ph)


def run_chart(rt, kind):
    pp, tgc = rt.mods["pinphone"], rt.mods["tgcharts"]
    ph, tr = make_phone(rt)
    ph.ledger.refresh()
    out = {"kind": kind}
    if kind == "bars":
        try:
            if hasattr(ph, "text_bars"):
                ph.text_bars()
            else:               # v-tg-rebuild step 10: /bars is a command module; its reply gathers the picture's numbers
                import importlib
                cm, cx = importlib.import_module("phone.command"), importlib.import_module("phone.context")
                cm.by_name("/bars").run(cx.Ctx.from_phone(ph, "/bars"))
        except Exception as e:                                  # noqa: BLE001
            out["bars_error"] = _err(e)
    try:
        ctx = ph._chart_ctx(kind, tgc)
        got = tgc.build(kind, ctx)
    except Exception as e:                                      # noqa: BLE001
        out["raised"] = _err(e)
        return out
    if not got:
        out["png"] = None
        return out
    data, caption = got
    out["sha256"] = C.sha(data)
    out["bytes"] = len(data)
    out["caption"] = caption
    if rt.out_dir:
        p = os.path.join(rt.out_dir, "charts", re.sub(r"[^A-Za-z0-9_.-]", "_", kind) + ".png")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)
        out["png"] = os.path.basename(p)
    return out


def _tick(rt, ph, label):
    n0 = len(ph.tg.sent)
    try:
        r = ph.alerts_tick()
        ret = [tname(x) for x in (r or [])]
        err = None
    except Exception as e:                                      # noqa: BLE001
        ret, err = None, _err(e)
    gl_fence.join_threads(rt.fence, 120)
    d = {"tick": label, "returned_types": ret, "sent": ph.tg.sent[n0:]}
    if err:
        d["raised"] = err
    return d


def run_tick(rt, which):
    pp = rt.mods["pinphone"]
    ph, tr = make_phone(rt)
    ticks = []
    if which == "update-flag":
        if rt.mode == "capture":
            return {"skipped": "capture never writes results/pinphone.update"}
        flag = pp.UPDATE_FLAG
        with open(flag, "w", encoding="utf-8") as fh:
            fh.write("golden\n")
        try:
            r = ph.update_flag_tick()
            out = {"reply": reply_view(pp, r)}
        except Exception as e:                                  # noqa: BLE001
            out = {"raised": _err(e)}
        gl_fence.join_threads(rt.fence, 120)
        out["sent"] = list(tr.sent)
        out["flag_left"] = os.path.exists(flag)
        out["exit_now"] = bool(getattr(ph, "_exit_now", False))
        return out
    if _TQ is not None and which in _TQ.TICKS:
        return _TQ.run(rt, ph, which, _tick)
    h0 = copy.deepcopy(rt.health0)
    ticks.append(_tick(rt, ph, "first (learns, sends nothing)"))
    if which == "alerts-state":
        h = copy.deepcopy(h0)
        h["alive"] = not h.get("alive")
        if not h["alive"]:
            h["pid"] = None
        rt.health = h
        ticks.append(_tick(rt, ph, "alive flipped to %s" % h["alive"]))
        rt.health = copy.deepcopy(h0)
        ticks.append(_tick(rt, ph, "back"))
        h = copy.deepcopy(h0)
        h["flag"] = "PAUSE golden"
        rt.health = h
        ticks.append(_tick(rt, ph, "stand-down flag set"))
    elif which == "alerts-recorder":
        for lab, k, f in (("Kalshi recorder silent", "kalshi_ok", False), ("both silent", "feeds_ok", False)):
            h = copy.deepcopy(rt.health)
            h[k] = f
            rt.health = h
            ticks.append(_tick(rt, ph, lab))
        rt.health = copy.deepcopy(h0)
        rt.health["kalshi_ok"] = rt.health["feeds_ok"] = True
        ticks.append(_tick(rt, ph, "both writing again"))
    elif which == "alerts-disk":
        for gb in (7.5, 5.9, 4.0, 9.5):
            h = copy.deepcopy(h0)
            h["disk_gb"] = gb
            rt.health = h
            ticks.append(_tick(rt, ph, "disk %.1f GB" % gb))
    elif which == "alerts-loss":
        losses = ph.ledger.losing_closes()
        if losses and isinstance(ph.seen_losses, set):
            ph.seen_losses.discard(losses[0][0])
            ticks.append(_tick(rt, ph, "the newest losing close is new"))
        else:
            ticks.append({"tick": "no losing close in the fixture"})
    elif which == "alerts-daily":
        ph.last_daily = "1999-01-01"
        ticks.append(_tick(rt, ph, "8 AM summary due"))
        ph.muted = True
        ph.last_daily = "1999-01-01"
        ticks.append(_tick(rt, ph, "muted: nothing"))
    return {"ticks": ticks, "last_state": ph.last_state, "last_rec": ph.last_rec, "disk_level": ph.disk_level}


def run_data(rt, which):
    pp, bs, tgc = rt.mods["pinphone"], rt.mods["botstats"], rt.mods.get("tgcharts")
    T = rt.clock.T
    if which == "all_bots":
        return {"all_bots": C.enc(bs.all_bots(now=T, getter=None, procs=rt.bs_procs_arg()))}
    if which == "active_bots":
        if not hasattr(bs, "active_bots"):
            return {"absent": "botstats.active_bots"}
        return {"active": list(bs.active_bots(procs=rt.bs_procs_arg(), now=T))}
    if which == "owner":
        return {"owner": owners(rt, bs)}
    if which == "version_of":
        out = {}
        for b in bs.BOTS:
            try:
                out[b] = C.enc(bs.version_of(b))
            except Exception as e:                              # noqa: BLE001
                out[b] = _err(e)
        return {"version_of": out}
    if which == "kind_of":
        cm = getattr(tgc, "CMD_KIND", {}) if tgc else {}
        return {"kind_of": {c: (tgc.kind_of(c) if tgc else None) for c in sorted(set(cm) | set(BASE_CMDS))}}
    if which == "tables":
        t = {}
        for mod, names in ((bs, ("BOTS", "SUBS", "SUB_POOL", "FX_PAIRS", "POT_POOL_ONLY", "POT_OWNER", "JB_SERIES",
                                 "PIN_HOURLY", "SPEC", "SUB_NAME", "HALT_KINDS", "FILL_KINDS", "ALWAYS_SHOWN", "PLAIN")),
                           (pp, ("FUNDS_WHAT", "FUNDS_BOTS", "FUNDS_SIZE_BOTS", "FUNDS_SHORT", "FUNDS_BOOKS", "BOT_CMDS",
                                 "BOT_CMD_OF", "BOT_WORD", "LADDER_GOAL_PCT", "SPEED_OTHERS", "SPEED_SKIPPED",
                                 "SPEED_LABEL", "FEATURE_BOT", "FEATURES", "HELP_BOT_LINES", "MAX_LEN")),
                           (tgc, ("CMD_KIND", "LEDGER_KINDS", "BOT_SHORT", "BOT_COLOUR", "BOT_ORDER", "ACCOUNT_NAME",
                                  "POT_WHAT"))):
            if mod is None:
                continue
            for n in names:
                if hasattr(mod, n):
                    t["%s.%s" % (mod.__name__, n)] = C.enc(getattr(mod, n))
        return {"tables": t}
    raise ValueError(which)


def owners(rt, bs):
    """owner(ticker, sub) for every ticker the fixture's botstats cache holds (settled + open), in its own sub, plus
    the synthetic tickers in every sub."""
    pairs = set()
    try:
        c = bs.load_cache()
        for sub, x in (c.get("subs") or {}).items():
            for k, r in (x.get("rows") or {}).items():
                pairs.add((str(sub), str((r or {}).get("ticker") or k.split("|")[0])))
            for p in (x.get("positions") or []):
                if isinstance(p, dict) and p.get("ticker"):
                    pairs.add((str(sub), str(p["ticker"])))
    except Exception as e:                                      # noqa: BLE001
        pairs.add(("err", _err(e)))
    subs = sorted(set(getattr(bs, "SUBS", ("0", "1", "2", "3", "4", "5"))))
    for s in subs:
        for tk in SYNTH_TICKERS:
            pairs.add((s, tk))
    out = {}
    for sub, tk in sorted(pairs):
        try:
            out["%s|%s" % (sub, tk)] = bs.owner(tk, sub)
        except Exception as e:                                  # noqa: BLE001
            out["%s|%s" % (sub, tk)] = _err(e)
    return out
