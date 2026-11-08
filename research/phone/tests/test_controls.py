"""test_controls.py -- phone/commands/controls.py (/pause /start /stop): the reply, the worker, busy, against Phone.control.

v-tg-rebuild step 9 (2026-10-30, lane D7). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_controls.py
NEVER the real controls: pindesk.do_start / do_pause / do_stop are replaced by recording stubs for the whole run (and the
test refuses to start if that did not take). time.sleep is planted (the worker's 3 s pause). KALS_TESTING=1.
v-tg-startyes (2026-11-07): a /start that would clear a halt (the drawdown brake, which also re-bases the high mark, or a
loss brake) only asks; '/start yes' does it, with the very health reading it judged handed to pindesk.do_start.
"""
import os
import sys
import tempfile
import threading
import time
import traceback
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import pindesk                                                       # noqa: E402

CALLS = []
_REAL = {n: getattr(pindesk, n) for n in ("do_start", "do_pause", "do_stop")}


def _stub(name, fail=None):
    def do(log=None, *a, **k):
        CALLS.append(name)
        if fail:
            raise RuntimeError(fail)
        if callable(log):
            log("stub %s ran" % name)
        for x in a:
            if callable(x):
                x("stub %s second channel" % name)
    return do


def plant(fail=None):
    for n in _REAL:
        setattr(pindesk, n, _stub(n, fail if n == "do_stop" else None))


plant()
from _legacy import pp, NEW                                         # noqa: E402  (pp: pinphone_legacy + NEW)
from phone import command as CM                                     # noqa: E402
from phone.commands import controls as K                            # noqa: E402
from phone.context import Ctx, FakeCtx                               # noqa: E402
from phone.html import Html                                          # noqa: E402

assert all(getattr(pindesk, n) is not _REAL[n] for n in _REAL), "the real pindesk controls are still in place"
pp.LOG = os.path.join(tempfile.mkdtemp(prefix="test_controls_"), "pinphone.log")   # log() lines land here
T = 1793448000.0
SLEPT = []
_REAL_SLEEP = time.sleep


def fake_sleep(s):
    SLEPT.append(s)


def wait_free(st, timeout=10.0):
    t_end = time.monotonic() + timeout
    while st.busy and time.monotonic() < t_end:
        _REAL_SLEEP(0.01)
    assert not st.busy, "the worker did not finish"


def _phone():
    """A legacy Phone on a planted ledger and health reading: the worker's closing /status page is the REAL one on both
    sides (legacy Phone.text_status vs phone/commands/status.py) -- v-tg-rebuild step 10 (the old stand-in planted
    text_status, which the new side no longer reaches)."""
    from _dlane import HEALTH, fake_ledger
    return pp.Phone({"chat_id": 7}, pp.FakeTelegram(), ledger=fake_ledger(), now_fn=lambda: T,
                    health_fn=lambda: dict(HEALTH))


def _status_world():
    """botstats failing (both of /status's every-pot lines are left out, logged) and hours up planted, on both sides."""
    import botstats
    from _dlane import boom, patched
    from phone.commands import day as D
    return patched((botstats, "all_bots", boom), (botstats, "active_bots", lambda procs=None: ["pin"]),
                   (pp, "hours_up_et_day", lambda day, until: 2.0), (D, "hours_up_et_day", lambda day, until: 2.0))


def test_replies_are_pinphones():
    assert {k: (type(v), str(v)) for k, v in K.CONTROL_REPLY.items()} == \
        {k: (type(v), str(v)) for k, v in pp.CONTROL_REPLY.items()}
    assert type(K.STOP_ASK) is type(pp.STOP_ASK) and str(K.STOP_ASK) == str(pp.STOP_ASK)


def test_pause_start_stop_vs_phone():
    """Each text on a fresh Phone (old) and on another fresh Phone through the module (new): the same reply, the same
    controls run, the same messages said by the worker (its 'x: ...' lines, then the /status page), busy freed."""
    saved = time.sleep
    time.sleep = fake_sleep
    world = _status_world()
    world.__enter__()
    try:
        # v-tg-step12 (lane R): '/pause now' is no longer the pin bot's pause (a word after /pause names ONE bot --
        # phone/commands/botctl.py; an unknown word changes nothing): test_botctl.py covers it; '/pause pin' is the pin's
        for text in ("/pause", "/start", "/start@kalsbot", "/stop yes", "/stop YES ", "/stop", "/stop no", "/pause pin"):
            out = []
            for side in ("old", "new"):
                ph = _phone()
                del CALLS[:]
                del SLEPT[:]
                if side == "old":
                    r = ph.handle(7, text)
                else:
                    c = Ctx.from_phone(ph, text)
                    r = CM.by_name(c.cmd).run(c)
                wait_free(ph)
                for t in list(threading.enumerate()):
                    if t is not threading.current_thread() and t.daemon and t.name.startswith("Thread"):
                        t.join(5)
                out.append((type(r).__name__, str(r), list(CALLS), list(SLEPT),
                            [(cid, type(m).__name__, str(m)) for cid, m in ph.tg.sent], ph.busy))
            assert out[0] == out[1], (text, out)
            assert not out[0][4] or "WATCHDOG" in out[0][4][-1][2].upper() or "Watchdog" in out[0][4][-1][2], out[0]
    finally:
        world.__exit__(None, None, None)
        time.sleep = saved


def test_worker_says_steps_then_status_and_frees_busy():
    saved = K.status_reply
    K.status_reply = lambda ctx: "STATUS"
    K.time = types.SimpleNamespace(sleep=fake_sleep)
    try:
        st = types.SimpleNamespace(busy=False)
        c = FakeCtx(text="/pause", state=st)
        del CALLS[:]
        del SLEPT[:]
        r = K.pause(c)
        assert r is K.CONTROL_REPLY["pause"]
        wait_free(st)
        assert CALLS == ["do_pause"] and SLEPT == [3]
        assert [t for _c, t in c.said] == ["pause: stub do_pause ran", "stub do_pause second channel", "STATUS"]
    finally:
        K.status_reply = saved
        K.time = time


def test_busy_answers_and_runs_nothing():
    st = types.SimpleNamespace(busy=True)
    del CALLS[:]
    for text in ("/pause", "/start", "/stop yes"):
        c = FakeCtx(text=text, state=st)
        assert CM.by_name(c.cmd).run(c) is K.CONTROL_REPLY["busy"]
    assert CALLS == [] and st.busy is True


def test_stop_without_yes_only_explains():
    st = types.SimpleNamespace(busy=False)
    for text in ("/stop", "/stop no", "/stop yess", "/stop  "):
        assert K.stop(FakeCtx(text=text, state=st)) is K.STOP_ASK and st.busy is False


def test_a_failing_control_is_said_and_frees_busy():
    plant(fail="boom")
    K.time = types.SimpleNamespace(sleep=fake_sleep)
    try:
        st = types.SimpleNamespace(busy=False)
        c = FakeCtx(text="/stop yes", state=st)
        assert K.stop(c) is K.CONTROL_REPLY["stop"]
        wait_free(st)
        assert [t for _c, t in c.said] == ["stop failed: boom"]
    finally:
        plant()
        K.time = time


def test_status_reply_falls_back_to_the_phone_until_d1_merges():
    st = types.SimpleNamespace(text_status=lambda: "OLD STATUS")
    try:
        __import__(K.STATUS_MODULE)
        have = True
    except ModuleNotFoundError:
        have = False
    if not have:
        assert K.status_reply(FakeCtx(text="/pause", state=st)) == "OLD STATUS"
    else:                                   # step 10: the /status Command runs, under the name /status
        assert CM.by_name("/status") is not None


# ---- v-tg-startyes (2026-11-07) -----------------------------------------------------------------------------------------
DD_WHY = "DRAWDOWN brake: bank $810.59 is 22.5% below its high of $1,046.43, limit 20%"
H_DD = {"alive": False, "pid": None, "flag": None, "quiet_s": None, "watchdog_s": 10, "open": {},
        "halt": {"kind": "halt", "t": T - 60, "why": DD_WHY}}
H_LOSS = dict(H_DD, halt={"kind": "halt", "t": T - 60, "why": "DAY loss cap: -$201.40 today >= $200"})
H_OK = {"alive": True, "pid": 4242, "flag": None, "quiet_s": 5, "watchdog_s": 10, "open": {}, "halt": None}
H_PAUSED = dict(H_DD, flag="operator PAUSE at 9:00 PM", halt=None)


def _start(text, health, st=None):
    """The reply to `text` on a FakeCtx whose health() is `health` (a dict, or an exception to raise); (reply, the
    arguments pindesk.do_start got, what was said)."""
    got = []
    saved = pindesk.do_start
    pindesk.do_start = lambda log, *a, **k: got.append(a)
    K.time = types.SimpleNamespace(sleep=fake_sleep)
    saved_status = K.status_reply
    K.status_reply = lambda ctx: "STATUS"
    try:
        st = st or types.SimpleNamespace(busy=False)
        kw = {"health": health} if not isinstance(health, Exception) else {}
        c = FakeCtx(text=text, now=T, state=st, **kw)
        if isinstance(health, Exception):
            c.health = lambda e=health: (_ for _ in ()).throw(e)
        was_busy = st.busy
        r = CM.by_name(c.cmd).run(c)
        if not was_busy:
            wait_free(st)
        return r, got, [t for _c, t in c.said]
    finally:
        pindesk.do_start = saved
        K.status_reply = saved_status
        K.time = time


def test_start_on_a_drawdown_halt_asks_first():
    r, got, said = _start("/start", dict(H_DD))
    w = str(r)
    assert "HALTED at its 20% drawdown brake" in w and "the bank is $810.59, 77% of its $1,046.43 high mark" in w, w
    assert "RE-BASES the high mark" in w and "<code>/start yes</code>" in w and "it stays halted" in w, w
    assert got == [] and said == [], "nothing started, nothing said"
    r, got, said = _start("/start yes", dict(H_DD))
    assert r is K.CONTROL_REPLY["start"] and len(got) == 1 and got[0][0]["halt"]["why"] == DD_WHY, got
    assert said[-1] == "STATUS"
    r, got, _s = _start("/start pin yes", dict(H_DD))
    assert r is K.CONTROL_REPLY["start"] and len(got) == 1, "'/start pin yes' is the same"
    r, got, _s = _start("/start pin", dict(H_DD))
    assert "HALTED" in str(r) and got == [], "'/start pin' asks too"


def test_start_on_a_loss_brake_asks_first():
    r, got, _s = _start("/start", dict(H_LOSS))
    assert "stopped by a safety brake</b>: DAY loss cap: -$201.40 today &gt;= $200" in str(r) and got == [], r
    r, got, _s = _start("/start yes", dict(H_LOSS))
    assert r is K.CONTROL_REPLY["start"] and len(got) == 1


def test_start_with_nothing_to_clear_starts_at_once():
    for h in (H_OK, H_PAUSED, {"alive": False, "pid": None, "flag": None, "quiet_s": None, "watchdog_s": 30,
                                "open": {}, "halt": None}):
        r, got, _s = _start("/start", dict(h))
        assert r is K.CONTROL_REPLY["start"] and len(got) == 1 and got[0][0] == h, (h, r)
        r, got, _s = _start("/start yes", dict(h))
        assert r is K.CONTROL_REPLY["start"] and len(got) == 1, "a 'yes' that was not needed starts as well"


def test_start_asks_when_the_state_cannot_be_read():
    with quiet_log():
        r, got, _s = _start("/start", RuntimeError("planted"))
        assert "could not read the pin bot's state" in str(r) and got == [], r
        r, got, _s = _start("/start yes", RuntimeError("planted"))
        assert r is K.CONTROL_REPLY["start"] and got == [()], "confirmed: do_start reads the state itself, as before"
        r, got, _s = _start("/start", {"halt": None})                # a reading missing its fields
        assert "could not read" in str(r) and got == []


def test_do_start_acts_on_the_reading_it_was_given():
    """The REAL pindesk.do_start, its world stubbed (no boot_all, no restart_bot, no flag touched): the re-base decision
    follows the health reading handed to it -- the one the operator confirmed -- never a fresh read (the 2026-11-07 tests
    review: do_start reading quick_health() whatever it was given passed every suite)."""
    td = tempfile.mkdtemp(prefix="test_controls_dostart_")
    flag = os.path.join(td, "pinrun-hwm.reset")
    ran = []
    stubs = {"_refuse_local": lambda what: None, "clear_flag": lambda: ran.append("clear_flag"),
             "_ps": lambda script, *a, **k: (ran.append(os.path.basename(script)), (0, ""))[1],
             "pinflat": types.SimpleNamespace(live_pid=lambda: 4242, pid_alive=lambda p: True),
             "RESET_FLAG": flag, "quick_health": None}
    saved = {n: getattr(pindesk, n) for n in stubs}
    try:
        for planted_quick, given, want in ((H_DD, dict(H_OK), False), (H_OK, dict(H_DD), True),
                                           (H_DD, None, True), (H_OK, None, False)):
            stubs["quick_health"] = (lambda q=planted_quick: dict(q))
            for n, v in stubs.items():
                setattr(pindesk, n, v)
            assert pindesk._ps is stubs["_ps"] and pindesk.pinflat is stubs["pinflat"], "never the real boot_all"
            if os.path.exists(flag):
                os.remove(flag)
            del ran[:]
            said = []
            assert _REAL["do_start"](said.append, given) is True
            assert os.path.exists(flag) is want, (given and given.get("halt"), planted_quick.get("halt"), said)
            assert ran == ["clear_flag", "boot_all.ps1"], ran
            assert any("re-base flag written" in s for s in said) is want, said
    finally:
        for n, v in saved.items():
            setattr(pindesk, n, v)


def test_start_busy_answers_busy_first():
    r, got, _s = _start("/start", dict(H_DD), st=types.SimpleNamespace(busy=True))
    assert r is K.CONTROL_REPLY["busy"] and got == []


def test_start_yes_is_not_a_bot_called_yes():
    assert not K._other_bot(FakeCtx(text="/start yes")) and K._other_bot(FakeCtx(text="/start jb"))
    assert K._other_bot(FakeCtx(text="/pause yes")), "only /start takes 'yes' for the pin bot"


class quiet_log:
    def __enter__(self):
        import contextlib
        import io
        self._r = contextlib.redirect_stdout(io.StringIO())
        self._r.__enter__()

    def __exit__(self, *a):
        self._r.__exit__(*a)


def test_declarations():
    for name, order in (("/pause", 10), ("/start", 20), ("/stop", 30)):
        c = CM.by_name(name)
        assert c.section == "controls" and c.order == order and c.runs_in_worker and c.kind_of(name) is None
    import tgcharts
    assert all(tgcharts.kind_of(n) is None for n in ("/pause", "/start", "/stop"))
    assert "/stop yes" in CM.by_name("/stop").examples


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
        for n, f in _REAL.items():
            setattr(pindesk, n, f)
    print("test_controls: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
