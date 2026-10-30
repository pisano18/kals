"""test_botctl.py -- /pause <bot>, /resume <bot> (/play, /start <bot>): phone/commands/botctl.py, controls' routing, and
phone/actions/{stopfiles,confirm,journal,launch}.py.

v-tg-step12 (2026-10-30, lane R). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_botctl.py
NOTHING REAL: botdata.paths.RESULTS is a temp folder for the whole run (every stop file, journal line and log lives
there); launch.SPAWN / WAIT are stubs (no process is ever started; the real ones refuse under KALS_TESTING=1, checked);
pindesk's controls are never reached (controls.control is replaced by a recorder); the worker's sleep is planted.
"""
import dataclasses
import json
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

from botdata import paths as P                                      # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_botctl_")
REAL_RESULTS = P.set_results(TMP)

import bots                                                          # noqa: E402
from phone import command as CM                                     # noqa: E402
from phone.actions import confirm as CF                              # noqa: E402
from phone.actions import journal as J                               # noqa: E402
from phone.actions import launch as L                                # noqa: E402
from phone.actions import stopfiles as SF                            # noqa: E402
from phone.commands import botctl as B                               # noqa: E402
from phone.commands import controls as K                             # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402

T = 1793448000.0            # 2026-10-30 14:40Z
JB_LIVE = (4242, r"C:\Python314\python.exe -u research\cleanroom\jumpband_live.py --live --subaccount 3 --max-contracts 5")
FX_LIVE = (4343, r"C:\Python314\python.exe -u research\cleanroom\fxtake_live.py --live")
SPAWNED, CONTROLS, SLEPT = [], [], []


def fake_spawn(cmdline, cwd):
    SPAWNED.append((cmdline, cwd))
    return 9001, None


L.SPAWN = fake_spawn
L.WAIT = lambda pid, timeout_s: 0
B.time = types.SimpleNamespace(sleep=lambda s: SLEPT.append(s), time=time.time)
K.control = lambda ctx, which: CONTROLS.append(which) or ("CONTROL " + which)


def open_bets(count=1, at_risk=4.40, ok=True):
    return lambda name: {"open": {"ok": ok, "count": count, "at_risk": at_risk, "error": None if ok else "HTTP 500"}}


def ctx(text, now=T, procs=(JB_LIVE, FX_LIVE), bs=None, chat=7):
    return FakeCtx(text=text, now=now, chat_id=chat, procs_fn=lambda p=procs: list(p),
                   bs_get=bs or open_bets(), state=types.SimpleNamespace(busy=False))


def run(text, **kw):
    c = ctx(text, **kw)
    return str(CM.by_name(c.cmd).run(c)), c


def clean():
    for f in os.listdir(TMP):
        os.remove(os.path.join(TMP, f))
    CF.drop()
    del SPAWNED[:], CONTROLS[:], SLEPT[:]


def stop(name):
    return os.path.join(TMP, bots.get(name).stop_file)


def journal():
    return J.read()


def wait_workers(timeout=10.0):
    t_end = time.monotonic() + timeout
    while B._BUSY and time.monotonic() < t_end:
        time.sleep(0.01)
    assert not B._BUSY, "the start worker did not finish"


# ---- names and routing ------------------------------------------------------------------------------------------------
def test_resolve_names():
    for w, n in (("jb", "jumpband"), ("/JumpBand", "jumpband"), ("fx", "fx"), ("fc", "forecaster"),
                 ("forecaster", "forecaster"), ("race", "race"), ("racestats", "race"), ("wx", "weather"),
                 ("ladder", "ladder"), ("pin", "pin")):
        assert B.resolve(w).name == n, w
    assert B.resolve("now") is None and B.resolve("") is None


def test_plain_pause_and_start_stay_the_pin_bots():
    clean()
    for text, which in (("/pause", "pause"), ("/pause pin", "pause"), ("/start", "start"), ("/start@kalsbot", "start"),
                        ("/start pin", "start"), ("/resume pin", "start"), ("/play pin", "start")):
        del CONTROLS[:]
        r, _c = run(text)
        assert CONTROLS == [which] and r == "CONTROL " + which, (text, CONTROLS, r)
    assert os.listdir(TMP) == [], "the pin bot's controls write no phone stop file"


def test_unknown_word_changes_nothing():
    clean()
    for text in ("/pause now", "/start soon", "/resume nosuch", "/play x"):
        r, _c = run(text)
        assert "No bot is called" in r and CONTROLS == [] and os.listdir(TMP) == [], (text, r)


# ---- pause ------------------------------------------------------------------------------------------------------------
def test_pause_asks_then_writes_the_stop_file():
    clean()
    r, _c = run("/pause jb")
    assert "Pause Jump band?" in r and "It holds 1 open bet ($4.40 at risk)." in r and "/pause jb yes" in r, r
    assert not os.path.exists(stop("jumpband")), "the question writes nothing"
    r, _c = run("/pause jb yes", now=T + 30)
    assert "Jump band paused" in r and os.path.exists(stop("jumpband")), r
    assert "still running with its stop file set" in r and "4242" in r, r       # STOPPING: the live copy still runs
    with open(stop("jumpband"), encoding="utf-8") as fh:
        assert "operator PAUSE of Jump band" in fh.read()
    j = journal()
    assert len(j) == 1 and j[0]["kind"] == "pause" and j[0]["bot"] == "jumpband" and j[0]["ok"] and j[0]["chat"] == 7
    # a second yes finds nothing waiting
    r, _c = run("/pause jb yes", now=T + 40)
    assert "already paused" in r, r


def test_pause_words_for_open_bets():
    clean()
    assert "It holds no open bets." in run("/pause fx", bs=open_bets(0))[0]
    assert "It holds 3 open bets ($12.00 at risk)." in run("/pause fx", bs=open_bets(3, 12.0))[0]
    assert "could not be read (HTTP 500)" in run("/pause fx", bs=open_bets(ok=False))[0]

    def boom(name):
        raise RuntimeError("botstats down")
    assert "Its open bets could not be read." in run("/pause fx", bs=boom)[0]


def test_yes_needs_a_question_in_time_and_for_that_bot():
    clean()
    r, _c = run("/pause jb yes")
    assert "Nothing is waiting" in r and not os.path.exists(stop("jumpband")), r
    run("/pause jb")
    r, _c = run("/pause jb yes", now=T + B.ASK_TTL_S + 1)
    assert "expired" in r and not os.path.exists(stop("jumpband")), r
    run("/pause jb")
    r, _c = run("/pause fx yes", now=T + 5)
    assert "another bot" in r and not os.path.exists(stop("fx")), r
    r, _c = run("/pause jb yes", now=T + 6, chat=8)
    assert "Nothing is waiting" in r, "another chat's yes (the router never lets one through anyway)"
    assert journal() == []


# ---- resume -----------------------------------------------------------------------------------------------------------
def test_resume_alone_lists_paused():
    clean()
    r, _c = run("/resume")
    assert "No bot is paused" in r, r
    SF.write("race", "test")
    SF.write("fx", "test")
    r, _c = run("/play")
    assert "Paused bots" in r and "Coin race (/race)" in r and "FX taker (/fx)" in r and "Jump band" not in r, r


def test_resume_keepalive_bot_removes_the_stop_file():
    clean()
    SF.write("fx", "operator PAUSE of FX taker")
    r, _c = run("/resume fx", procs=(JB_LIVE,))
    assert "Resume FX taker?" in r and "operator PAUSE of FX taker" in r and "keep-alive" in r and "/resume fx yes" in r
    assert os.path.exists(stop("fx"))
    r, _c = run("/resume fx yes", procs=(JB_LIVE,), now=T + 10)
    assert "FX taker resumed" in r and not os.path.exists(stop("fx")) and "boot_all" in r, r
    assert "not running and no stop file" in r, r                                   # DOWN until boot_all's next pass
    assert SPAWNED == [], "a keep-alive bot is never started by the phone"
    j = journal()
    assert [x["kind"] for x in j] == ["resume"] and j[0]["removed"] is True


def test_resume_running_bot_with_stop_file():
    clean()
    SF.write("fx", "test")
    run("/resume fx")
    r, _c = run("/resume fx yes", now=T + 1)
    assert "still running and trades again" in r and "running, no stop file" in r, r


def test_already_running_and_nothing_to_resume():
    clean()
    assert "already running" in run("/resume jb")[0]
    r, _c = run("/resume ladder", procs=())
    assert "has no stop file, so there is nothing to resume" in r, r


def test_resume_jumpband_starts_it_through_its_recipe():
    clean()
    SF.write("jumpband", "stop line: $-25.10 settled since the first live record is at or under $-25.00")
    with open(os.path.join(TMP, "jb_deploy.ps1"), "w", encoding="utf-8") as fh:
        fh.write("# stand-in\n")
    with open(os.path.join(TMP, "jb_deploy.out"), "w", encoding="utf-8") as fh:
        fh.write("2026-10-30 10:00:00 stage live; HEAD abc\n2026-10-30 10:00:01 LIVE launched: return 0 pid 5555\n")
    r, _c = run("/resume jb", procs=(FX_LIVE,))
    assert "Resume Jump band?" in r and "jb_deploy.ps1 -Stage live" in r and "STOP LINE" in r, r
    r, c = run("/resume jb yes", procs=(FX_LIVE,), now=T + 20)
    assert "Starting Jump band" in r and not os.path.exists(stop("jumpband")), r
    wait_workers()
    assert len(SPAWNED) == 1, SPAWNED
    cl, cwd = SPAWNED[0]
    assert cl == 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%s" -Stage live' % os.path.join(TMP, "jb_deploy.ps1")
    assert cwd == P.REPO and SLEPT == [45]
    said = [str(t) for _c, t in c.said]
    assert "pid 9001" in said[0] and "LIVE launched" in said[-1] and "Jump band" in said[-1], said
    kinds = [x["kind"] for x in journal()]
    assert kinds == ["resume", "start"] and journal()[1]["pid"] == 9001, journal()


def test_resume_jumpband_down_without_stop_file_offers_the_start():
    clean()
    with open(os.path.join(TMP, "jb_deploy.ps1"), "w", encoding="utf-8") as fh:
        fh.write("# stand-in\n")
    r, _c = run("/resume jb", procs=())
    assert "It has no stop file and is not running." in r and "/resume jb yes" in r, r
    run("/resume jb yes", procs=(), now=T + 1)
    wait_workers()
    assert len(SPAWNED) == 1


def test_a_failed_launch_is_said():
    clean()
    with open(os.path.join(TMP, "jb_deploy.ps1"), "w", encoding="utf-8") as fh:
        fh.write("# stand-in\n")
    saved = L.SPAWN
    L.SPAWN = lambda cl, cwd: (None, "WMI refused (return 2)")
    try:
        run("/resume jb", procs=())
        _r, c = run("/resume jb yes", procs=(), now=T + 1)
        wait_workers()
        assert [str(t) for _c, t in c.said] == ["start Jump band failed: WMI refused (return 2)"], c.said
        assert journal()[-1]["kind"] == "start" and journal()[-1]["ok"] is False
    finally:
        L.SPAWN = saved


def test_no_recipe_no_guess():
    clean()
    jb = bots.get("jumpband")
    bare = dataclasses.replace(jb, start=None)
    saved = B.resolve
    B.resolve = lambda w: bare if w == "jb" else saved(w)
    try:
        SF.write("jumpband", "test")
        r, _c = run("/resume jb", procs=())
        assert "no keep-alive and no start recipe" in r and "Nothing changed" in r and os.path.exists(stop("jumpband"))
        r, _c = run("/resume jb yes", procs=())
        assert os.path.exists(stop("jumpband")) and SPAWNED == [], r
    finally:
        B.resolve = saved


def test_missing_recipe_script_is_said():
    clean()
    SF.write("jumpband", "test")
    run("/resume jb", procs=())
    r, _c = run("/resume jb yes", procs=(), now=T + 1)
    assert "cannot run" in r and "not there" in r and SPAWNED == [], r


# ---- the actions' own rails -------------------------------------------------------------------------------------------
def test_real_launcher_and_live_stop_files_refuse_in_tests():
    assert P.testing()
    pid, err = L.wmi_create("cmd /c echo hi", P.REPO)
    assert pid is None and "KALS_TESTING" in err
    old = P.set_results(REAL_RESULTS)
    try:
        for fn in (lambda: SF.write("fx", "x"), lambda: SF.remove("fx")):
            try:
                fn()
            except P.WriteFenced:
                pass
            else:
                raise AssertionError("a stop file in the live results folder was not refused")
    finally:
        P.set_results(old)
    for fn in (lambda: SF.write("pin", "x"), lambda: SF.remove("pin")):
        try:
            fn()
        except ValueError:
            pass
        else:
            raise AssertionError("the pin bot's flag is pindesk's")


def test_command_lines_are_fixed():
    p = os.path.join(TMP, "x.ps1")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("#\n")
    assert L.ps_file_cmdline(p, ("-Stage", "live")).endswith('x.ps1" -Stage live')
    for args in (("-Stage", "live; rm x"), ("a b",), ('"q"',), ("$(x)",), ("a|b",), ("",)):
        try:
            L.ps_file_cmdline(p, args)
        except ValueError:
            continue
        raise AssertionError("an argument got through: %r" % (args,))
    for bad in (r"C:\Windows\x.ps1", os.path.join(TMP, "..", "x.ps1"), os.path.join(TMP, "x.bat")):
        try:
            L.ps_file_cmdline(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    for name in ("..\\x.ps1", "C:\\x.ps1", "nothere.ps1", "x.txt", ""):
        try:
            L.resolve_script(name)
        except ValueError:
            continue
        raise AssertionError(name)
    assert L.resolve_script("x.ps1") == p


def test_confirm_codes_and_tries():
    CF.drop()
    saved = CF.CODE
    CF.CODE = lambda: "4821"
    try:
        assert CF.ask(1, "k", "a", T, 60, plan={"x": 1}, code=True) == "4821"
        assert CF.take(1, "k", T + 1, code="1111") == (None, "code")
        assert CF.take(1, "k", T + 1, code="2222") == (None, "code")
        got, why = CF.take(1, "k", T + 2, code=" 4821 ")
        assert why is None and got["plan"] == {"x": 1}
        assert CF.take(1, "k", T + 3, code="4821") == (None, "nothing"), "single use"
        CF.ask(1, "k", "a", T, 60, code=True)
        for _ in range(CF.MAX_BAD):
            CF.take(1, "k", T + 1, code="0000")
        assert CF.take(1, "k", T + 1, code="4821") == (None, "nothing"), "three wrong codes drop it"
        CF.ask(1, "k", "a", T, 60)
        assert CF.take(1, "k", T + 61) == (None, "expired")
    finally:
        CF.CODE = saved
    assert len(CF.new_code()) == 4 and 1000 <= int(CF.new_code()) <= 9999


def test_journal_never_raises():
    old = P.set_results(REAL_RESULTS)
    try:
        assert J.record("test", x=1) is False, "the live journal is fenced in a test"
    finally:
        P.set_results(old)
    assert J.record("test", t=T, x=1) is True and J.read(kinds=("test",))[-1]["x"] == 1


def test_declaration_and_help():
    c = CM.of_module("phone.commands.botctl")
    assert len(c) == 1 and c[0].names == ("/resume", "/play") and c[0].section == "controls" and c[0].chart is None
    assert "/pause jb" in c[0].help_line and "/resume jb" in c[0].help_line
    import tgcharts
    assert all(tgcharts.kind_of(n) is None for n in ("/resume", "/play"))


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
            except Exception:                                   # noqa: BLE001
                failed.append(name)
                print("  FAIL %s\n%s" % (name, traceback.format_exc()), flush=True)
    finally:
        P.set_results(REAL_RESULTS)
    print("test_botctl: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
