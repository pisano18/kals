"""test_logfiles.py -- research/logfiles.py and the readers research/log_rotate.py's archive must not hide history from
(ops fixes, 2026-11-07).

log_rotate.py moves a finished log into results\\archive\\<name>.gz. Each test plants a log, reads it plain, archives it
with log_rotate's OWN archive_one (the exclusive open, the gzip, the read-back check, the delete) and reads it again:
the answer must be the same, and a log read while plain must not be counted twice once archived.
THE CLASS RULES (test_class_rules_over_every_reader, widened 11-07 after the review): 1) no research file globs a
rotated family (log_rotate.POLICY, written out or held in a constant) past logfiles.glob, except the exact CALLS in
EXEMPT, each with its reason; 2) no builtin open() of a path that may be archived (followed by data flow through the
file); 3) no bare stat of a listed log outside a try (log_rotate may archive it between the listing and the look).
test_class_rules_catch_what_they_are_for plants a break of each, the review's surviving mutations among them.
Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_logfiles.py   (botstats.py --selftest runs it too)
"""
import ast
import calendar
import collections
import gzip
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import _kit                                                          # noqa: E402  (sys.path, KALS_TESTING=1)
from _kit import ck, sandbox                                         # noqa: E402

import logfiles                                                      # noqa: E402
import log_rotate                                                    # noqa: E402
from botdata import filefold, logs                                   # noqa: E402

RESEARCH = _kit.RESEARCH
T0 = calendar.timegm((2026, 9, 25, 12, 0, 0))


def _r(kind, t, **kw):
    kw.update(kind=kind, t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)))
    return kw


def _pin_log(td, stamp, recs, age_days=70):
    p = os.path.join(td, "pinrun-live-%s.jsonl" % stamp)
    with open(p, "w", encoding="utf-8", newline="") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    mt = time.time() - age_days * 86400
    os.utime(p, (mt, mt))
    return p


def _archive(path):
    """log_rotate's own move; returns the .gz path."""
    st = os.stat(path)
    ad = logfiles.archive_dir(os.path.dirname(path))
    os.makedirs(ad, exist_ok=True)
    got, info = log_rotate.archive_one(path, st.st_size, st.st_mtime, ad, lambda m: None)
    ck(got == "moved" and not os.path.exists(path), "archived %s (%s)" % (os.path.basename(path), info))
    return os.path.join(ad, os.path.basename(path) + ".gz")


def _recs(t, tk="KXBTC15M-26SEP250815-15"):
    return [_r("start", t, code_sha="abc", ws_later_fall_c=10.0, hedge_jump_max=8.0, max_positions=3),
            _r("signal", t + 10, ticker=tk, want="no", price=0.97, size=10.0, tau=20),
            _r("order", t + 11, ticker=tk, filled=10.0, exec_price=0.97, status="executed", body={"count": 10}),
            _r("hedge", t + 30, ticker=tk, side="yes", n=10.0, price=0.05, status="executed", asked=10.0),
            _r("autosize", t + 40, new=88, why="bank $1000.00"),
            _r("settled", t + 900, ticker=tk, want="no", result="no", cost=0.97, pnl_c=30.0, realised=0.3)]


def test_logfiles_glob_and_open_through_an_archive():
    with sandbox() as td:
        ps = [_pin_log(td, "20260925T120000Z", _recs(T0)), _pin_log(td, "20260926T120000Z", _recs(T0 + 86400)),
              _pin_log(td, "20260927T120000Z", _recs(T0 + 2 * 86400), age_days=0)]
        before = [open(p, "rb").read() for p in ps]
        gz = _archive(ps[1])
        got = logfiles.glob(os.path.join(td, "pinrun-live-*.jsonl"))
        ck([logfiles.log_name(p) for p in got] == [os.path.basename(p) for p in ps] and got[1] == gz,
           "logfiles.glob: plain + archived, in start order")
        ck([logfiles.read_bytes(p) for p in got] == before, "the archived log reads back byte for byte")
        with logfiles.open(gz, encoding="utf-8") as fh:
            ck([json.loads(x)["kind"] for x in fh] == [r["kind"] for r in _recs(0)], "logfiles.open reads it as text")
        ck(abs(os.path.getmtime(gz) - (time.time() - 70 * 86400)) < 5, "the archive keeps the log's modified time")
        ck(logfiles.resolve(td, os.path.basename(ps[1])) == gz, "resolve finds a log by name in the archive")
        # a run cut between the archive write and the delete leaves BOTH: listed once, the plain one (review F1)
        with open(ps[1], "wb") as fh:
            fh.write(before[1])
        both = logfiles.glob(os.path.join(td, "pinrun-live-*.jsonl"))
        ck(both == ps and not any(logfiles.is_gz(p) for p in both),
           "a log both plain and archived is listed ONCE, as the plain file (never read twice)")


def test_botdata_readers_answer_the_same_from_an_archive():
    with sandbox() as td:
        p = _pin_log(td, "20260925T120000Z", _recs(T0))
        _pin_log(td, "20261101T120000Z", _recs(T0 + 40 * 86400), age_days=0)
        since0 = logs.read_since(p, T0 + 5)
        last0 = logs.last_record(p, ("autosize",))
        feed = []
        st0, _e = filefold.fold(p, "t", lambda: {"n": 0}, lambda s, ln: (s.update(n=s["n"] + 1), feed.append(ln)),
                                dict)
        gz = _archive(p)
        ck(logs.read_since(gz, T0 + 5) == since0 and len(since0) == 5, "read_since: the same 5 records from the .gz")
        ck(logs.last_record(gz, ("autosize",)) == last0 and last0["new"] == 88, "last_record: the same record")
        ck(logs.last_record(gz, ("nope",)) is None, "last_record: NULL kind -> None")
        n0 = len(feed)
        st1, e1 = filefold.fold(gz, "t", lambda: {"n": 0}, lambda s, ln: (s.update(n=s["n"] + 1), feed.append(ln)),
                                dict)
        ck(st1 == st0 == {"n": 6} and len(feed) == 2 * n0, "filefold: the same fold, every line fed once")
        st2, _e = filefold.fold(gz, "t", lambda: {"n": 0}, lambda s, ln: (s.update(n=s["n"] + 1), feed.append(ln)),
                                dict)
        ck(st2 == st0 and len(feed) == 2 * n0, "...and a second call reads nothing (an archive never changes)")
        plain = logs.pin_logs()
        both = logs.pin_logs(archived=True)
        ck(len(plain) == 1 and len(both) == 2 and both[0] == gz, "pin_logs: plain only by default; archived=True "
                                                                 "adds the archive, oldest first")


def test_fixes_and_rules_watch_read_an_archive():
    from botdata import fixes
    import pinrules_watch as rw
    with sandbox() as td:
        p = _pin_log(td, "20260925T120000Z", _recs(T0))
        cur = _pin_log(td, "20261101T120000Z", _recs(T0 + 40 * 86400), age_days=0)
        L0, S0 = rw.Logs([p]), fixes.Scan([p])
        gz = _archive(p)
        L1, S1 = rw.Logs([gz]), fixes.Scan([gz])
        ck(len(L1.starts) == len(L0.starts) == 1 and L1.settled == L0.settled and len(L1.orders) == len(L0.orders) == 1
           and L1.hedges == L0.hedges, "pinrules_watch.Logs: the same starts, orders, hedges and settles from the .gz")
        strip = lambda d: {k: [{f: v for f, v in r.items() if f != "_path"} for r in rs] for k, rs in d.items()}  # noqa: E731
        ck(len(S1.starts) == len(S0.starts) == 1 and strip(S1.settled) == strip(S0.settled) != {}
           and all(r["_path"] == gz for rs in S1.settled.values() for r in rs),
           "fixes.Scan: the same records from the .gz (each tagged with the path it was read from)")
        ck(fixes.pin_paths(T0) == [gz, cur], "fixes.pin_paths: a fix tracked from 09-25 still reads its first log "
                                             "after it is archived")


def test_bars_reads_an_archive():
    import bars
    with sandbox() as td:
        p = _pin_log(td, "20260925T120000Z", _recs(T0))
        r0 = bars.load_run(p, T0)
        t0 = bars._tail_t(p)
        gz = _archive(p)
        r1 = bars.load_run(gz, T0)
        ck(bars._stamp_of(gz) == T0 and bars._stamp_of(p) == T0, "bars._stamp_of reads the stamp of a .gz too")
        ck(bars._tail_t(gz) == t0 and t0 == T0 + 900, "bars._tail_t: the last record's time from the .gz")
        ck({k: r1[k] for k in ("start", "lo", "hi", "settled")} == {k: r0[k] for k in ("start", "lo", "hi", "settled")},
           "bars.load_run: the same run from the .gz")
        ck([x["start"]["t"] for x in bars.live_runs(td, T0)] == [r0["start"]["t"]], "bars.live_runs still finds it")


def test_desk_ledger_reads_an_archive_once():
    import pindesk
    with sandbox() as td:
        p = _pin_log(td, "20260925T120000Z", _recs(T0))
        _pin_log(td, "20261101T120000Z", _recs(T0 + 40 * 86400), age_days=0)
        led = pindesk.Ledger(results=td)
        led.refresh()
        n0 = len(led.orders)
        gz = _archive(p)
        led.refresh()
        ck(n0 == 2 and len(led.orders) == n0, "a log read while plain is NOT read again once archived (2 orders, "
                                               "not %d)" % len(led.orders))
        fresh = pindesk.Ledger(results=td)
        fresh.refresh()
        ck(len(fresh.orders) == 2 and sorted(o["file"] for o in fresh.orders) == [
            "pinrun-live-20260925T120000Z.jsonl", "pinrun-live-20261101T120000Z.jsonl"] and gz in fresh.files,
           "a fresh Ledger reads the archive once, and an order keeps its log's own name (no .gz)")
        fresh.refresh()
        ck(len(fresh.orders) == 2, "...and never again")


def test_phone_speed_tail_rows_reads_an_archive_once():
    from phone.commands import speed
    with sandbox() as td:
        p = _pin_log(td, "20260925T120000Z", _recs(T0))
        want = speed.tail_rows(p, "kind", "settled")
        gz = _archive(p)
        try:
            got = speed.tail_rows(gz, "kind", "settled")
            again = speed.tail_rows(gz, "kind", "settled")
            ck(got == want and len(got) == 1 and again is got, "speed.tail_rows: the same rows, read once")
        finally:
            for k in [k for k in speed._TAILS if k[0] in (p, gz)]:
                speed._TAILS.pop(k, None)


def test_rotation_ages_outlast_every_window_that_skips_the_archive():
    """The readers left on plain logs only (botdata.activity, the phone's day windows, bots/pin.py's newest log) are
    right only while every window they read is SHORTER than the age at which pin's logs are archived."""
    from botdata import series, money
    live = [f for f in log_rotate.POLICY if f.pattern == "pinrun-live-*.jsonl"]
    longest = max(series.WINDOW_DAYS, series.LONG_DAYS, money.LAST_DAYS)
    ck(len(live) == 1 and live[0].min_age_s >= (longest + 7) * 86400,
       "pin's logs are archived after %d days, a week past the phone's longest window (%d days)"
       % (live[0].min_age_s / 86400, longest))
    ck(all(f.min_age_s >= 2 * 86400 for f in log_rotate.POLICY) and log_rotate.HARD_FLOOR_S >= 86400,
       "nothing is archived before 48 h, and never inside 24 h")


# ---- THE CLASS RULES (2026-11-07, widened after the review: 17 of 40 mutations of the first version survived) ----------
# Three rules over every research file (tests, _attic, the bots' own copies and the two rotation modules skipped):
#   1. no glob of a rotated family past logfiles.glob -- the pattern written out OR held in a constant
#      (LIVE_PAT = "pinrun-live-*.jsonl"; GLOB = os.path.join(R, LIVE_PAT)) -- except the CALLS listed in EXEMPT, each
#      with its reason and its exact argument text and count (a new direct glob in an exempt file still fails);
#   2. no builtin open() of a path that came from logfiles.glob / resolve / pin_paths / pin_logs(archived=True) --
#      followed through assignments, loops, comprehensions, returns and calls into the same file's functions and
#      classes -- unless it sits in the plain branch of an is_gz / .gz test (a .gz read by open() is gzip bytes read as
#      text, silently);
#   3. no bare os.path.getmtime / getsize / os.stat of a LISTED log (a direct glob too), nor a sort / max keyed on one,
#      outside a try: log_rotate can archive an old log between the listing and that look (logfiles.mtime /
#      logfiles.by_mtime are the safe forms).
EXEMPT = {
    "bots/pin.py": ("the newest log only (bet size, loss gauge, books)",
                    {'os.path.join(si.results, "pinrun-live-*.jsonl")': 1,
                     'os.path.join(wi.results, "pinrun-live-*.jsonl")': 2}),
    "earlyhindsight.py": ("FROZEN: its sha256 is registered as bar B1's scorer in results/FREEZE_bars.json; its "
                          "freeze-window live logs are git-tracked, so log_rotate never moves them",
                          {'os.path.join(results_dir, "pinrun-live-*.jsonl")': 1,
                           'os.path.join(results_dir, "pinrun-paper-*.jsonl")': 1}),
    "golden/gl_ticks_q.py": ("the newest log's name only", {'os.path.join(_results(), "pinrun-live-*.jsonl")': 1}),
    "kalshi_watch.py": ("the newest live log only, and the one the scan before was reading (v-kwatch, 11-07): "
                        "log_rotate never archives the newest of a family, nor one written in the last 24 h",
                        {'env.path("pinrun-live-*.jsonl")': 1}),
    "pindesk.py": ("the newest live log (three health reads) and paper arms written in the last 15 minutes",
                   {'os.path.join(RESULTS, "pinrun-live-*.jsonl")': 3, 'os.path.join(RESULTS, "pinrun-paper-*.jsonl")': 1}),
    "pinflat.py": ("the newest log only", {'os.path.join(results, "pinrun-live-*.jsonl")': 1}),
    "pinrules_watch.py": ("the probe of the 3 newest logs (pin_paths reads the archive)",
                          {'os.path.join(RESULTS, "pinrun-live-*.jsonl")': 1}),
    "pintool.py": ("the newest log only", {'os.path.join(RESULTS, "pinrun-live-*.jsonl")': 1}),
    "pinwhatif.py": ("the paper logs still being written (modified within --stale-s)",
                     {'os.path.join(RESULTS, "pinrun-paper-*.jsonl")': 1}),
    "server_sync.py": ("copies results\\ top folder to the laptop by design, and the newest log's age",
                       {'_os.path.join(results, "pinrun-live-*.jsonl")': 1}),
    "sweptwatch.py": ("the 3 newest logs", {"GLOB": 1}),
    "watchlive.py": ("the newest log only", {'os.path.join(root, "results", "pinrun-live-*.jsonl")': 1}),
}
_SKIP = re.compile(r"(^|[\\/])(tests|_attic)([\\/]|$)|^pinrun(913|_afternoon)?\.py$|^pinvin_|^logfiles\.py$|"
                   r"^log_rotate\.py$|^pinphone_legacy\.py$")
FAMS = [f.pattern for f in log_rotate.POLICY]
_GLOBS = {"glob.glob", "_glob.glob", "dirlist.glob", "_dirlist.glob", "glob.iglob", "_glob.iglob", "iglob"}
_STATS = {"os.path.getmtime", "os.path.getsize", "os.stat", "_os.path.getmtime", "_os.path.getsize", "_os.stat"}
_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _dotted(e):
    parts = []
    while isinstance(e, ast.Attribute):
        parts.append(e.attr)
        e = e.value
    if isinstance(e, ast.Name):
        return ".".join([e.id] + parts[::-1])
    return None


class Scan:
    """One file's paths to rotated logs, by data flow: which names hold a listing of a rotated family (`archived`:
    one that may hold a .gz -- rules 2; else any listing -- rule 3), and where each rule is broken."""

    def __init__(self, src):
        self.tree = ast.parse(src)
        self.lines = src.splitlines(True)
        self.parent, self._scope, self._chain = {}, {}, {}
        stack = [(self.tree, None)]
        while stack:
            n, sc = stack.pop()
            inner = n if isinstance(n, _FUNCS) else sc
            for c in ast.iter_child_nodes(n):
                self.parent[c], self._scope[c] = n, inner
                stack.append((c, inner))
        self.nodes = list(ast.walk(self.tree))
        self.lf = {"logfiles"} | {a.asname for n in self.nodes if isinstance(n, ast.Import) for a in n.names
                                  if a.name == "logfiles" and a.asname}
        # a MODULE constant (UPPER_CASE) holding a family pattern, or built from one: LIVE_PAT, GLOB, LIVE_GLOB ...
        self.consts, changed = set(), True
        assigns = [(n, self.seg(n.value)) for n in self.tree.body if isinstance(n, ast.Assign)
                   and all(isinstance(t, ast.Name) and t.id.isupper() for t in n.targets)]
        while changed:
            changed = False
            for n, v in assigns:
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id not in self.consts and self.mentions(v):
                        self.consts.add(t.id)
                        changed = True
        self.funcs, self.classes = {}, {}
        for n in self.nodes:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs.setdefault(n.name, []).append(n)
            elif isinstance(n, ast.ClassDef):
                self.classes[n.name] = n

    def seg(self, e):
        a, b = e.lineno - 1, e.end_lineno - 1
        if a == b:
            return self.lines[a][e.col_offset:e.end_col_offset]
        return "".join([self.lines[a][e.col_offset:]] + self.lines[a + 1:b] + [self.lines[b][:e.end_col_offset]])

    def mentions(self, text):
        return any(f in text for f in FAMS) or any(re.search(r"\b%s\b" % re.escape(c), text) for c in self.consts)

    def scope(self, n):
        return self._scope.get(n)

    def chain(self, n):
        s0 = self.scope(n)
        c = self._chain.get(s0)
        if c is None:
            out, s = [], s0
            while s is not None:
                out.append(s)
                s = self.scope(s)
            c = self._chain[s0] = out + [None]
        return c

    def direct_globs(self):
        """[(line, argument text)] for every glob call (not logfiles.glob) of a rotated family."""
        out = []
        for n in self.nodes:
            if isinstance(n, ast.Call) and (_dotted(n.func) or "") in _GLOBS and n.args:
                a = " ".join(self.seg(n.args[0]).split())
                if self.mentions(a):
                    out.append((n.lineno, a))
        return out

    def seed(self, call):
        d = _dotted(call.func) or ""
        head, _sep, attr = d.rpartition(".")
        if head in self.lf and attr in ("glob", "resolve"):
            return True
        if attr == "pin_paths" or d == "pin_paths":
            return True
        if attr == "pin_logs" or d == "pin_logs":
            return not self.archived or any(k.arg == "archived" and not (isinstance(k.value, ast.Constant)
                                                                         and k.value.value is False)
                                            for k in call.keywords)
        return (not self.archived and d in _GLOBS and bool(call.args) and self.mentions(self.seg(call.args[0])))

    def run(self, archived):
        self.archived, self.tainted, self.returns = archived, set(), set()
        while True:
            n0 = (len(self.tainted), len(self.returns))
            for n in self.nodes:
                if isinstance(n, ast.Assign) and self.is_t(n.value):
                    for t in n.targets:
                        self.taint(t, n)
                elif isinstance(n, (ast.AugAssign, ast.AnnAssign)) and n.value is not None and self.is_t(n.value):
                    self.taint(n.target, n)
                elif isinstance(n, (ast.For, ast.AsyncFor)) and self.is_t(n.iter):
                    self.taint(n.target, n)
                elif isinstance(n, ast.comprehension) and self.is_t(n.iter):
                    self.taint(n.target, n)
                elif isinstance(n, ast.Return) and n.value is not None and self.is_t(n.value):
                    s = self.scope(n)
                    if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.returns.add(s.name)
                elif isinstance(n, ast.Call):
                    for fd, off in self.callee(n):
                        ps = [a.arg for a in fd.args.posonlyargs + fd.args.args][off:]
                        for i, a in enumerate(n.args):
                            if i < len(ps) and self.is_t(a):
                                self.tainted.add((fd, ps[i]))
                        for k in n.keywords:
                            if k.arg in ps and self.is_t(k.value):
                                self.tainted.add((fd, k.arg))
            if (len(self.tainted), len(self.returns)) == n0:
                return self

    def taint(self, target, at):
        for x in ast.walk(target):
            if isinstance(x, ast.Name):
                self.tainted.add((self.scope(at), x.id))

    def callee(self, call):
        """[(FunctionDef, params to skip)] a call reaches in this file: a function, a method on self / cls, a class."""
        f = call.func
        if isinstance(f, ast.Name):
            if f.id in self.classes:
                return [(fd, 1) for fd in self.funcs.get("__init__", []) if self.parent.get(fd) is self.classes[f.id]]
            return [(fd, 0) for fd in self.funcs.get(f.id, [])]
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ("self", "cls"):
            return [(fd, 1) for fd in self.funcs.get(f.attr, [])]
        return []

    def is_t(self, e):
        if isinstance(e, ast.Call):
            if self.seed(e):
                return True
            d = _dotted(e.func) or ""
            if d.split(".")[-1] in self.returns and (d.count(".") == 0 or d.startswith(("self.", "cls."))):
                return True
            return d in ("sorted", "list", "reversed", "tuple", "set", "filter") and any(self.is_t(a) for a in e.args)
        if isinstance(e, ast.Name):
            return any((s, e.id) in self.tainted for s in self.chain(e))
        if isinstance(e, (ast.Subscript, ast.Starred)):
            return self.is_t(e.value)
        if isinstance(e, (ast.List, ast.Tuple, ast.Set)):
            return any(self.is_t(x) for x in e.elts)
        if isinstance(e, ast.BinOp):
            return self.is_t(e.left) or self.is_t(e.right)
        if isinstance(e, ast.IfExp):
            return self.is_t(e.body) or self.is_t(e.orelse)
        if isinstance(e, ast.BoolOp):
            return any(self.is_t(v) for v in e.values)
        if isinstance(e, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
            return self.is_t(e.elt)
        return False

    def _under(self, n, test):
        c, p = n, self.parent.get(n)
        while p is not None:
            if test(c, p):
                return True
            c, p = p, self.parent.get(p)
        return False

    def builtin_opens(self):
        """Rule 2: lines of a builtin open() for reading of an archived-capable path, outside an is_gz / .gz branch."""
        self.run(archived=True)
        gz = re.compile(r"is_gz|\.gz|\bgz\b")
        out = []
        for n in self.nodes:
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open" and n.args:
                mode = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "mode"), None)
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and set(mode.value) & set("wax+"):
                    continue
                if self.is_t(n.args[0]) and not self._under(n, lambda c, p: isinstance(p, (ast.If, ast.IfExp))
                                                             and bool(gz.search(self.seg(p.test)))):
                    out.append(n.lineno)
        return out

    def bare_stats(self):
        """Rule 3: lines of a stat of a listed log, or a sort / max keyed on one, outside a try."""
        self.run(archived=False)

        def tried(c, p):
            return isinstance(p, ast.Try) and bool(p.handlers) and c in p.body
        out = set()
        for n in self.nodes:
            if not isinstance(n, ast.Call) or self._under(n, tried):
                continue
            if (_dotted(n.func) or "") in _STATS and n.args and self.is_t(n.args[0]):
                out.add(n.lineno)
            for k in n.keywords:
                if k.arg == "key" and (_dotted(k.value) or "") in _STATS:
                    tgt = n.args[0] if n.args else (n.func.value if isinstance(n.func, ast.Attribute) else None)
                    if tgt is not None and self.is_t(tgt):
                        out.add(n.lineno)
        return sorted(out)


def _sources():
    """(relative path, source) of every research file the rules cover."""
    for root, dirs, files in os.walk(RESEARCH):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "tests", "_attic")]
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(root, fn), RESEARCH).replace("\\", "/")
            if _SKIP.search(rel):
                continue
            try:
                src = open(os.path.join(root, fn), encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if any(k in src for k in ["logfiles", "pin_paths", "pin_logs"] + FAMS):
                yield rel, src


def _globs_broken(rel, src):
    """Rule 1 for one file: the direct globs that are not on its EXEMPT list."""
    found = collections.Counter(a for _ln, a in Scan(src).direct_globs())
    allowed = collections.Counter((EXEMPT.get(rel) or ("", {}))[1])
    return ["%s: %s (x%d)" % (rel, a, n - allowed[a]) for a, n in found.items() if n > allowed[a]]


def test_class_rules_over_every_reader():
    hits1, hits2, hits3, seen = [], [], [], {}
    for rel, src in _sources():
        try:
            s = Scan(src)
        except SyntaxError:
            continue
        seen[rel] = collections.Counter(a for _ln, a in s.direct_globs())
        hits1 += _globs_broken(rel, src)
        hits2 += ["%s:%d" % (rel, ln) for ln in s.builtin_opens()]
        hits3 += ["%s:%d" % (rel, ln) for ln in s.bare_stats()]
    ck(not hits1, "RULE 1: no reader globs a rotated family past logfiles.glob outside EXEMPT (%d: %s)"
       % (len(hits1), hits1[:6]))
    ck(not hits2, "RULE 2: no builtin open() of a log that may be archived (%d: %s)" % (len(hits2), hits2[:6]))
    ck(not hits3, "RULE 3: no bare stat of a listed log outside a try (%d: %s)" % (len(hits3), hits3[:6]))
    stale = ["%s: %s" % (f, a) for f, (_why, calls) in EXEMPT.items() for a in calls if not (seen.get(f) or {}).get(a)]
    ck(not stale, "every EXEMPT call is still there (a stale entry would hide a new one): %s" % stale[:4])


def test_class_rules_catch_what_they_are_for():
    """Each rule finds a planted break -- the review's surviving mutations among them -- and passes the safe forms."""
    r5 = ('LIVE_PAT = "pinrun-live-*.jsonl"\n'
          'def report(results):\n    return sorted(glob.glob(os.path.join(results, LIVE_PAT)))\n')
    ck([a for _ln, a in Scan(r5).direct_globs()] == ["os.path.join(results, LIVE_PAT)"],
       "RULE 1 finds a family held in a constant (pinday.report reverted to glob.glob(LIVE_PAT): R5)")
    r3 = ('def tick():\n    probe = sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl")))[-3:]\n'
          'def pin_paths(t):\n    return sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl")))\n')
    ck(_globs_broken("pinrules_watch.py", r3) == ['pinrules_watch.py: os.path.join(RESULTS, "pinrun-live-*.jsonl") (x1)'],
       "RULE 1: an exempt file's SECOND direct glob still fails (pinrules_watch.pin_paths reverted: R3)")
    ck(Scan('x = logfiles.glob(os.path.join(R, "pinrun-paper-*.jsonl"))\n').direct_globs() == [],
       "RULE 1 passes logfiles.glob")
    r7 = ('import logfiles\n'
          'def read_jsonl(path):\n    fh = open(path, encoding="utf-8")\n    return fh\n'
          'def load_live(d):\n    for f in logfiles.glob(os.path.join(d, "pinrun-live-*.jsonl")):\n        read_jsonl(f)\n')
    ck(Scan(r7).builtin_opens() == [3], "RULE 2 follows a listed path into a helper's builtin open() (barcheck."
                                        "read_jsonl reverted: R7)")
    ok7 = r7.replace("fh = open(path", "fh = logfiles.open(path")
    ck(Scan(ok7).builtin_opens() == [], "RULE 2 passes logfiles.open")
    cls = ('import logfiles\nclass Logs:\n    def __init__(self, paths):\n        for p in paths:\n'
           '            with open(p) as fh:\n                pass\n'
           'def pin_paths(t):\n    return logfiles.glob("x/pinrun-live-*.jsonl")\n'
           'def go():\n    Logs(pin_paths(0))\n')
    ck(Scan(cls).builtin_opens() == [5], "RULE 2 follows a returned listing into a class (pinrules_watch.Logs)")
    plain = ('import logfiles\ndef tail(path):\n    if logfiles.is_gz(path):\n        return logfiles.read_bytes(path)\n'
             '    else:\n        return open(path, "rb").read()\n'
             'def go():\n    for p in logfiles.glob("pinrun-live-*.jsonl"):\n        tail(p)\n'
             '        open(p + ".csv", "w")\n')
    ck(Scan(plain).builtin_opens() == [], "RULE 2 passes the plain branch of an is_gz test and a write")
    st = ('def newest(r):\n    logs = glob.glob(os.path.join(r, "pinrun-live-*.jsonl"))\n'
          '    return max(logs, key=os.path.getmtime)\n'
          'def fresh(r):\n    return [p for p in logfiles.glob("pinrun-paper-*.jsonl") if os.path.getmtime(p) > 0]\n'
          'def safe(r):\n    for p in logfiles.glob("pinrun-paper-*.jsonl"):\n        try:\n'
          '            os.path.getmtime(p)\n        except OSError:\n            pass\n'
          '    return max(logfiles.glob("pinrun-paper-*.jsonl"), key=logfiles.by_mtime)\n')
    ck(Scan(st).bare_stats() == [3, 5], "RULE 3 finds max(key=getmtime) and a bare getmtime filter over a listing "
                                        "(pinflat.newest_log, pinrules_watch.pin_paths before 11-07), and passes a try "
                                        "and logfiles.by_mtime")


def test_readers_survive_a_log_archived_since_the_listing():
    """The rule-3 class at work: a listing that names a log gone by the time it is looked at (log_rotate moved it) is
    skipped, never a crash -- pinflat's newest log, /activity's pin logs, changes_watch."""
    import pinflat
    import changes_watch as cw
    from botdata import activity, logs as blogs
    with sandbox() as td:
        live = _pin_log(td, "20261101T120000Z", _recs(T0 + 40 * 86400), age_days=0)
        gone = os.path.join(td, "pinrun-live-20260901T000000Z.jsonl")         # listed, then archived
        real_glob = pinflat.glob.glob
        pinflat.glob.glob = lambda pat: [gone, live] if "pinrun-live-" in pat else real_glob(pat)
        try:
            ck(pinflat.newest_log(td) == live, "pinflat.newest_log: a log gone since the listing is never the newest "
                                               "(and no crash)")
        finally:
            pinflat.glob.glob = real_glob
        real_pin_logs = blogs.pin_logs
        blogs.pin_logs = lambda *a, **k: [gone, live]
        try:
            out = activity.activity("pin", T0)
            ck(out["ok"] and out["source"] == [os.path.basename(live)], "botdata.activity: the gone log is skipped "
                                                                         "(%s)" % out["source"])
        finally:
            blogs.pin_logs = real_pin_logs
        real_lf_glob = cw.logfiles.glob
        cw.logfiles.glob = lambda pat, globber=None: [gone, live] if "-live-" in pat else []
        try:
            ck(cw.live_files(1, results=td) == [live] and cw.traj_result({"KXBTC15M-X"}, results=td) == {}
               and cw.read_logs([gone, live]) is not None,
               "changes_watch: live_files / traj_result / read_logs skip the gone log")
        finally:
            cw.logfiles.glob = real_lf_glob


if __name__ == "__main__":
    sys.exit(_kit.run(dict(globals()), "test_logfiles"))
