"""test_approve.py -- /approve: phone/commands/approve.py and phone/actions/approvals.py, and the real manifest.

v-tg-step12 (2026-10-30, lane R). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_approve.py
NOTHING REAL RUNS: botdata.paths.RESULTS is a temp folder (the manifest, the scripts, their logs, state.json and the
journal live there); launch.SPAWN / WAIT are stubs (no process starts; the real one refuses under KALS_TESTING=1). The
repo's own results\\approvals\\approvals.json is only READ (test_the_real_manifest).
"""
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

from botdata import paths as P                                      # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_approve_")
REAL_RESULTS = P.set_results(TMP)

from phone import command as CM                                     # noqa: E402
from phone.actions import approvals as A                             # noqa: E402
from phone.actions import confirm as CF                              # noqa: E402
from phone.actions import journal as J                               # noqa: E402
from phone.actions import launch as L                                # noqa: E402
from phone.commands import approve as AP                             # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402

T = 1793448000.0
SPAWNED = []
EXIT = {"code": 0}


def fake_spawn(cmdline, cwd):
    SPAWNED.append((cmdline, cwd))
    with open(os.path.join(TMP, "x.out"), "a", encoding="utf-8") as fh:     # what the script would log
        fh.write("2026-10-30 10:00:00 CHANGED restart_bot.ps1\n2026-10-30 10:00:01 restart launched\n")
    return 7001, None


L.SPAWN = fake_spawn
L.WAIT = lambda pid, timeout_s: EXIT["code"]
CF.CODE = lambda: "4821"
SCRIPT = "# the change\r\nWrite-Output 'hi'\r\n"


def setup(items=None, script=SCRIPT):
    for f in os.listdir(TMP):
        p = os.path.join(TMP, f)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    CF.drop()
    del SPAWNED[:]
    EXIT["code"] = 0
    with open(os.path.join(TMP, "x.ps1"), "w", encoding="utf-8", newline="") as fh:
        fh.write(script)
    with open(os.path.join(TMP, "x.out"), "w", encoding="utf-8") as fh:
        fh.write("2026-10-29 09:00:00 an older run\n")
    os.makedirs(os.path.join(TMP, "approvals"))
    sha = A.text_sha(os.path.join(TMP, "x.ps1"))
    base = {"id": "x1", "title": "Pin: a change", "description": "Does a thing.", "stop_rule": "Undo it if bad.",
            "script": "x.ps1", "log": "x.out", "added_by": "test", "date": "2026-10-30", "sha256": sha}
    its = [dict(base, **kw) for kw in (items or [{}])]
    with open(os.path.join(TMP, "approvals", "approvals.json"), "w", encoding="utf-8") as fh:
        json.dump({"items": its}, fh)
    return sha


def ctx(text, now=T, chat=7):
    return FakeCtx(text=text, now=now, chat_id=chat)


def run(text, **kw):
    c = ctx(text, **kw)
    return str(CM.by_name(c.cmd).run(c)), c


def wait_workers(timeout=10.0):
    t_end = time.monotonic() + timeout
    while AP._BUSY and time.monotonic() < t_end:
        time.sleep(0.01)
    assert not AP._BUSY


def test_list_show_and_run_once():
    setup()
    r, _c = run("/approve")
    assert "Waiting changes (1)" in r and "x1" in r and "Pin: a change" in r and "/approve x1" in r, r
    r, _c = run("/approve x1")
    assert "Does a thing." in r and "Stop rule:" in r and "Undo it if bad." in r and "/approve x1 yes 4821" in r, r
    assert SPAWNED == []
    r, c = run("/approve x1 yes 4821", now=T + 60)
    assert "Running x1" in r, r
    wait_workers()
    assert len(SPAWNED) == 1
    cl, cwd = SPAWNED[0]
    assert cl == 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%s"' % os.path.join(TMP, "x.ps1") and cwd == P.REPO
    said = [str(t) for _c, t in c.said]
    assert "x1 started (pid 7001" in said[0] and "exit code 0" in said[-1] and "restart launched" in said[-1], said
    assert "an older run" not in said[-1], "only the log's NEW lines"
    st = A.read_state()["x1"]
    assert st["status"] == "done" and st["exit"] == 0 and st["pid"] == 7001 and st["chat"] == 7, st
    assert [x["kind"] for x in J.read()] == ["approve", "approve_start", "approve_done"]
    # once only
    r, _c = run("/approve x1")
    assert "Already ran" in r and "runs only once" in r, r
    r, _c = run("/approve")
    assert "No change is waiting" in r and "Already run" in r, r
    CF.ask(7, "approve", "x1", T, 600, code=True)
    r, _c = run("/approve x1 yes 4821", now=T + 1)
    assert "runs only once" in r and len(SPAWNED) == 1, r


def test_code_rules():
    setup()
    r, _c = run("/approve x1 yes 4821")
    assert "Nothing is waiting" in r and SPAWNED == [], r
    run("/approve x1")
    r, _c = run("/approve x1 yes 1234", now=T + 1)
    assert "not the code" in r and SPAWNED == [], r
    r, _c = run("/approve x1 yes", now=T + 2)
    assert "not the code" in r and SPAWNED == [], r
    r, _c = run("/approve x1 yes 4821", now=T + AP.ASK_TTL_S + 5)
    assert "expired" in r and SPAWNED == [], r
    assert not os.path.exists(A.state_path())


def test_changed_script_is_not_run():
    setup()
    run("/approve x1")
    with open(os.path.join(TMP, "x.ps1"), "a", encoding="utf-8") as fh:
        fh.write("Remove-Item C:\\important\n")
    r, _c = run("/approve x1 yes 4821", now=T + 1)
    assert "changed after it was listed" in r and SPAWNED == [], r
    r, _c = run("/approve x1", now=T + 2)
    assert "It cannot run" in r and "yes" not in r.split("cannot run")[1], r


def test_line_endings_do_not_matter():
    sha = setup()
    with open(os.path.join(TMP, "x.ps1"), "w", encoding="utf-8", newline="") as fh:
        fh.write("\ufeff" + SCRIPT.replace("\r\n", "\n"))
    assert A.text_sha(os.path.join(TMP, "x.ps1")) == sha


def test_bad_entries_refused():
    setup([{"id": "a1", "script": "..\\evil.ps1"}, {"id": "a2", "script": "C:\\Windows\\x.ps1"},
           {"id": "a3", "script": "x.out"}, {"id": "a4", "args": ["-Force"]}, {"id": "A5"}, {"id": "a6", "title": ""},
           {"id": "a7", "script": "nothere.ps1"}, {"id": "a1"}])
    items, why = A.load()
    assert why is None and len(items) == 8
    for it in items:
        path, why = A.check(it)
        assert path is None and why, it["id"]
    for ident in ("a1", "a2", "a3", "a4", "a7"):
        r, _c = run("/approve %s" % ident)
        assert "It cannot run" in r, (ident, r)
    assert "No waiting change is called" in run("/approve a5")[0]
    assert SPAWNED == []


def test_no_manifest_and_unknown_id():
    setup()
    os.remove(os.path.join(TMP, "approvals", "approvals.json"))
    assert "No waiting changes" in run("/approve")[0]
    setup()
    assert "No waiting change is called <b>zz</b>" in run("/approve zz")[0]


def test_failed_start_may_be_tried_again():
    setup()
    saved = L.SPAWN
    L.SPAWN = lambda cl, cwd: (None, "WMI refused (return 9)")
    try:
        run("/approve x1")
        _r, c = run("/approve x1 yes 4821", now=T + 1)
        wait_workers()
        assert "could not start" in str(c.said[-1][1]) and A.read_state()["x1"]["status"] == "failed_to_start"
    finally:
        L.SPAWN = saved
    r, _c = run("/approve x1", now=T + 2)
    assert "/approve x1 yes 4821" in r, r
    run("/approve x1 yes 4821", now=T + 3)
    wait_workers()
    assert len(SPAWNED) == 1 and A.read_state()["x1"]["status"] == "done"


def test_still_running_after_the_wait():
    setup()
    EXIT["code"] = None
    run("/approve x1")
    _r, c = run("/approve x1 yes 4821", now=T + 1)
    wait_workers()
    assert "still running after 30 minutes" in str(c.said[-1][1])
    assert A.read_state()["x1"]["status"] == "running", "never run again"


def test_superseded_never_runs():
    """v-fx-onepot: an item a later one replaces ('superseded_by') is listed apart and refused, its code never asked."""
    setup([{"id": "old1", "superseded_by": "new1"}, {"id": "new1"}])
    r, _c = run("/approve")
    assert "Waiting changes (1)" in r and "<b>new1</b>" in r and "Replaced</b> (not run)" in r, r
    assert "old1 — Pin: a change: superseded by new1" in r, r
    r, _c = run("/approve old1")
    assert "It cannot run" in r and "superseded by new1" in r and "yes" not in r.split("It cannot run")[1], r
    _r, _c = run("/approve old1 yes 4821", now=T + 1)
    assert SPAWNED == []
    path, why = A.check(A.find(A.load()[0], "new1"))
    assert path is not None and why is None, why


def test_the_real_manifest():
    """The repo's results\\approvals\\approvals.json: pin15, fx30 (superseded by fxonepot) and fxonepot, each script's
    sha matching its file."""
    old = P.set_results(os.path.join(P.REPO, "results"))
    try:
        items, why = A.load()
        assert why is None, why
        by = {it["id"]: it for it in items}
        assert {"pin15", "fx30", "fxonepot", "pinsize"} <= set(by), list(by)
        for it in items:                                  # every listed item runs, or says it was replaced
            path, why = A.check(it)
            assert (path is not None and why is None) or it.get("superseded_by"), (it["id"], why)
        it = by["pin15"]
        assert it["script"] == "pin_size15_nohedgejump.ps1" and it["log"] == "pin_size15.out"
        assert "-$100" in it["stop_rule"] and "4.00" in it["stop_rule"]
        ps = by["pinsize"]                                # v-pinsize (10-30 evening): size only, the jump hedge kept
        assert ps["script"] == "pin_size133.ps1" and "jump hedge" in ps["title"].lower() and "-$100" in ps["stop_rule"]
        fx30, one = by["fx30"], by["fxonepot"]
        assert fx30["superseded_by"] == "fxonepot" and A.check(fx30) == (None, "superseded by fxonepot: run that one instead")
        assert one["script"] == "fx_onepot_restart.ps1" and one["log"] == "fx_onepot_restart.out"
        assert "NO MONEY MOVE IS NEEDED" in one["description"] and "sub5pool0" in one["description"]
        path, why = A.check(one)
        assert path is not None and why is None, why
    finally:
        P.set_results(old)


def test_declaration():
    c = CM.of_module("phone.commands.approve")
    assert len(c) == 1 and c[0].names == ("/approve",) and c[0].section == "controls" and c[0].chart is None
    import tgcharts
    assert tgcharts.kind_of("/approve") is None


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
    print("test_approve: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
