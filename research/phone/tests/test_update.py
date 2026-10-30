"""test_update.py -- phone/commands/update.py: /update's self-test gate (its exact command lines: DESIGN risk 2), the
answers, _updating / _exit_now, and the update-flag tick, against Phone.text_update / update_flag_tick.

v-tg-rebuild step 9 (2026-10-30, lane D7). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_update.py
NOTHING RUNS: subprocess.run is replaced by a recorder for the whole run (the gate's self-tests are never started).
The flag file is a temp file. KALS_TESTING=1.
"""
import os
import subprocess
import sys
import tempfile
import time
import traceback
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import pinphone as pp                                                # noqa: E402
from phone import command as CM                                     # noqa: E402
from phone.commands import update as U                              # noqa: E402
from phone.context import Ctx, FakeCtx                               # noqa: E402
from phone.html import Html                                          # noqa: E402

T = 1793448000.0
TMP = tempfile.mkdtemp(prefix="test_update_")
pp.LOG = os.path.join(TMP, "pinphone.log")
_REAL_RUN = subprocess.run
RUNS = []
EXIT = {"pinphone.py": 0, "botstats.py": 0}


def fake_run(args, **kw):
    RUNS.append((list(args), kw))
    rc = EXIT[os.path.basename(args[2])]
    if isinstance(rc, BaseException):
        raise rc
    return subprocess.CompletedProcess(args, rc, "", "")


subprocess.run = fake_run


def wait_done(st, timeout=10.0):
    t_end = time.monotonic() + timeout
    while getattr(st, "_updating", False) and time.monotonic() < t_end:
        time.sleep(0.01)
    assert not getattr(st, "_updating", False), "the update worker did not finish"


def _phone():
    led = types.SimpleNamespace(results=TMP, refresh=lambda: None)
    return pp.Phone({"chat_id": 7}, pp.FakeTelegram(), ledger=led, now_fn=lambda: T)


def test_the_gate_command_lines_never_change():
    del RUNS[:]
    EXIT.update({"pinphone.py": 0, "botstats.py": 0})
    st = types.SimpleNamespace()
    c = FakeCtx(text="/update", state=st, chat_id=7)
    U.start_update(c)
    wait_done(st)
    assert U.RESEARCH == pp.HERE
    want = [([sys.executable, "-u", os.path.join(pp.HERE, f), "--selftest"],
             dict(cwd=os.path.dirname(pp.HERE), capture_output=True, text=True, encoding="utf-8", errors="replace",
                  timeout=900)) for f in ("pinphone.py", "botstats.py")]
    assert RUNS == want, RUNS


def test_answers_vs_phone():
    """pass / one fails / both fail / the run raises: the same reply, the same messages said (to the same chat), the
    same _exit_now, _updating freed -- the old Phone and the module side by side."""
    for exits in ({"pinphone.py": 0, "botstats.py": 0}, {"pinphone.py": 0, "botstats.py": 1},
                  {"pinphone.py": 2, "botstats.py": 1}, {"pinphone.py": subprocess.TimeoutExpired("x", 900),
                                                         "botstats.py": 0}):
        out = []
        for side in ("old", "new"):
            EXIT.update(exits)
            del RUNS[:]
            ph = _phone()
            if side == "old":
                r = ph.handle(7, "/update")
            else:
                c = Ctx.from_phone(ph, "/update")
                r = CM.by_name("/update").run(c)
            wait_done(ph)
            out.append((type(r).__name__, str(r), [(cid, type(m).__name__, str(m)) for cid, m in ph.tg.sent],
                        bool(getattr(ph, "_exit_now", False)), ph._updating, [a for a, _k in RUNS]))
        assert out[0] == out[1], (exits, out)
    EXIT.update({"pinphone.py": 0, "botstats.py": 0})


def test_words():
    EXIT.update({"pinphone.py": 0, "botstats.py": 1})
    st = types.SimpleNamespace()
    c = FakeCtx(text="/update", state=st, chat_id=7)
    r = U.start_update(c)
    assert isinstance(r, Html) and str(r) == "🔄 <b>Checking the newest phone code</b> (self-test, a few minutes)…"
    wait_done(st)
    assert c.said == [(7, Html("⚠️ <b>Update NOT applied</b>: the new code failed its self-test: botstats.py (exit 1). "
                               "The phone keeps running the old code."))] and not getattr(st, "_exit_now", False)
    st._updating = True
    assert str(U.start_update(FakeCtx(text="/update", state=st))) == "🔄 An update check is already running."
    EXIT.update({"pinphone.py": 0, "botstats.py": 0})


def test_flag_tick_vs_phone():
    """No flag -> None; the flag -> removed first, /update runs once, the reply says it came from the file and is said
    once; a second tick -> None. The old Phone (its UPDATE_FLAG patched) and the module (ctx.pp's UPDATE_FLAG)."""
    flag = os.path.join(TMP, "pinphone.update")
    saved = pp.UPDATE_FLAG
    pp.UPDATE_FLAG = flag
    try:
        out = []
        for side in ("old", "new"):
            ph = _phone()
            tick = ph.update_flag_tick if side == "old" else (lambda: U.flag_tick(Ctx.from_phone(ph)))
            r0 = tick()
            with open(flag, "w", encoding="utf-8") as fh:
                fh.write("go\n")
            r1 = tick()
            wait_done(ph)
            r2 = tick()
            out.append((r0, type(r1).__name__, str(r1), r2, os.path.exists(flag),
                        [(cid, str(m)) for cid, m in ph.tg.sent], bool(getattr(ph, "_exit_now", False))))
        assert out[0] == out[1], out
        assert "asked for by the update flag file, not a message" in out[1][2] and not out[1][4]
    finally:
        pp.UPDATE_FLAG = saved


def test_flag_tick_unpaired_or_planted_start():
    flag = os.path.join(TMP, "pinphone2.update")
    with open(flag, "w", encoding="utf-8") as fh:
        fh.write("go\n")
    fake_pp = types.SimpleNamespace(UPDATE_FLAG=flag)
    assert U.flag_tick(FakeCtx(pp=fake_pp, chat_id=None)) is None and os.path.exists(flag), "no paired chat: untouched"
    ups = []
    c = FakeCtx(pp=fake_pp, chat_id=7)
    r = U.flag_tick(c, start=lambda ctx: (ups.append(1), Html("🔄 <b>Checking</b>"))[1])
    assert ups == [1] and not os.path.exists(flag) and str(r).startswith("🔄 <b>Checking</b>\n<i>asked for by")
    assert c.said == [(None, r)] and U.flag_tick(c) is None


def test_declaration():
    c = CM.by_name("/update")
    assert c.section == "controls" and c.order == 50 and c.runs_in_worker and c.kind_of() is None


def main():
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    t0 = time.time()
    try:
        for name, fn in tests:
            try:
                fn()
                passed += 1
                print("  ok   %s" % name, flush=True)
            except Exception:                                       # noqa: BLE001
                failed.append(name)
                print("  FAIL %s\n%s" % (name, traceback.format_exc()), flush=True)
    finally:
        subprocess.run = _REAL_RUN
    print("test_update: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
