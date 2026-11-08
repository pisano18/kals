"""test_rotation.py -- phone/rotation.py: the server's log rotation on the phone (ops fixes, 2026-11-07). One alert when
it turns bad (never ran, stuck, stale, failed, git unreadable, the disk within 8 weeks of the 6 GB line), nothing more
while it stays that way, one when it works again; nothing at all when it is not installed; its line on /server.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_rotation.py   (exit 0 = every test passed)
A temp results folder (botdata.paths) with planted status files and log_rotate's own runs; a fake clock. KALS_TESTING=1;
no network.
"""
import collections
import json
import os
import sys
import tempfile
import time
import traceback
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import log_rotate as LR                                              # noqa: E402
from botdata import paths                                            # noqa: E402
from phone import log as plog                                        # noqa: E402
from phone import monitor as M                                       # noqa: E402
from phone import rotation as R                                      # noqa: E402
from phone.commands.server import page as PG                         # noqa: E402
from phone.html import tg_html_problems                              # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_rotation_")
paths.set_results(TMP)
plog.set_path(lambda: os.path.join(TMP, "pinphone.log"), replace=True)
T0 = 1794050400.0               # 2026-11-07 11:20Z = 6:20 AM ET (EST)
Disk = collections.namedtuple("Disk", "total used free")
MACH = {"host": "EC2AMAZ-TEST", "ncpu": 2, "cpu": 23.4, "py_cpu": 18.2, "py_n": 14, "py_mem": 1.6e9,     # test_server's
        "mem_total": 4.0e9, "mem_avail": 1.1e9, "mem_load": 72, "commit": 3.1e9, "commit_limit": 5.2e9,
        "disk_free": 31.2e9, "disk_total": 53.7e9, "uptime_s": 6120.0, "reboot": False, "reboot_why": None,
        "sample_s": 0.5, "errs": []}


def clear():
    for n in os.listdir(TMP):
        p = os.path.join(TMP, n)
        if os.path.isfile(p) and n != "pinphone.log":
            os.remove(p)


def put(name, rec):
    with open(os.path.join(TMP, name), "w", encoding="utf-8") as fh:
        json.dump(rec, fh)


def status(**kw):
    rec = {"t": T0 - 2 * 3600, "state": "done", "started_t": T0 - 2 * 3600, "finished_t": T0 - 2 * 3600 + 40,
           "ok": True, "errors": [], "git": "read", "moved": 12, "raw_mb": 1234.0, "gz_mb": 98.0, "freed_mb": 1136.0,
           "free_gb": 25.7, "gb_week": 1.14, "weeks_to_guard": 17.3, "weeks_to_empty": 22.5,
           "rate_from": "measured over the last 9 days of runs", "kept": {}}
    rec.update(kw)
    put(LR.STATUS_NAME, rec)


class Rig:
    def __init__(self):
        self.m = M.MonitorState()
        self.sent = []
        self.ctx = types.SimpleNamespace()

    def check(self, t):
        before = len(self.sent)
        M.check_rotation(self.ctx, self.m, lambda msg, urgent=False: self.sent.append((str(msg), urgent)), t)
        return self.sent[before:]


def test_not_installed_says_nothing():
    clear()
    r = Rig()
    assert r.check(T0) == [] and r.check(T0 + 3600) == []
    assert R.server_lines(R.health(T0), T0) == []
    assert R.server_lines(None, T0) == []


def test_each_bad_state_alerts_once_and_then_once_when_ok_again():
    cases = [("never", lambda: put(LR.INSTALLED_NAME, {"installed_t": T0 - 40 * 3600}), "has never run"),
             ("stuck", lambda: status(state="running", started_t=T0 - 4 * 3600), "got stuck"),
             ("stale", lambda: status(finished_t=T0 - 50 * 3600), "has not run for 2 days 2 h"),
             ("failed", lambda: status(ok=False, errors=["pintraj-live-x.jsonl: could not write the archive: disk"]),
              "hit an error"),
             ("nogit", lambda: status(git="unreadable"), "moved nothing"),
             ("short", lambda: status(weeks_to_guard=5.2), "about 5 weeks left to the 6 GB line")]
    for state, plant, words in cases:
        clear()
        plant()
        assert R.health(T0)["state"] == state, (state, R.health(T0))
        r = Rig()
        got = r.check(T0)
        assert len(got) == 1 and words in got[0][0] and got[0][1] is False, (state, got)     # not urgent
        assert tg_html_problems(got[0][0]) == [], (state, tg_html_problems(got[0][0]))
        assert "\u2014" not in got[0][0] and " ET" in got[0][0] or state == "short", (state, got[0][0])
        assert r.check(T0 + 10) == [], state                                  # read at most every 5 min
        assert r.check(T0 + R.CHECK_EVERY_S) == [], state                     # the same state: told once
        clear()
        status(finished_t=T0 + R.CHECK_EVERY_S * 2 - 60)
        back = r.check(T0 + R.CHECK_EVERY_S * 2)
        assert len(back) == 1 and back[0][0].startswith("✅ <b>Log rotation is working again</b>: its 6:29 AM ET run "
                                                        "moved 12 file(s) and freed 1,136 MB."), (state, back)
        assert r.check(T0 + R.CHECK_EVERY_S * 3) == [], state


def test_a_bad_state_changing_to_another_is_told_and_running_is_not_ok():
    clear()
    r = Rig()
    status(git="unreadable")
    assert len(r.check(T0)) == 1
    status(ok=False, errors=["x: y"])
    got = r.check(T0 + R.CHECK_EVERY_S)
    assert len(got) == 1 and "hit an error" in got[0][0], got
    status(state="running", started_t=T0 + R.CHECK_EVERY_S * 2 - 60)
    assert r.check(T0 + R.CHECK_EVERY_S * 2) == [] and r.m.rot_bad == "failed"   # running: not yet ok
    status(finished_t=T0 + R.CHECK_EVERY_S * 3 - 30)
    assert len(r.check(T0 + R.CHECK_EVERY_S * 3)) == 1 and r.m.rot_bad is None


def test_uninstalled_forgets():
    clear()
    r = Rig()
    status(git="unreadable")
    r.check(T0)
    clear()
    assert r.check(T0 + R.CHECK_EVERY_S) == [] and r.m.rot_bad is None


def test_a_real_run_that_could_not_ask_git_alerts():
    clear()
    with open(os.path.join(TMP, "pinrun-paper-20261001T000000Z.jsonl"), "w", encoding="utf-8") as fh:
        fh.write("{}\n")
    os.utime(os.path.join(TMP, "pinrun-paper-20261001T000000Z.jsonl"), (T0 - 9 * 86400, T0 - 9 * 86400))
    with open(os.path.join(TMP, "pinrun-paper-20261105T000000Z.jsonl"), "w", encoding="utf-8") as fh:
        fh.write("{}\n")
    LR.run(results=TMP, repo=TMP, apply=True, now_fn=lambda: T0, sleep_fn=lambda s: None,
           disk_fn=lambda p: Disk(0, 0, 40e9), tracked_fn=lambda r, d: None, out=lambda m: None)
    r = Rig()
    got = r.check(T0 + 60)
    assert len(got) == 1 and "Log rotation moved nothing</b> on its 6:20 AM ET run" in got[0][0], got
    assert "40.0 GB free, filling about 1.46 GB a week: about 23 weeks to the 6 GB line" in got[0][0], got
    LR.run(results=TMP, repo=TMP, apply=True, now_fn=lambda: T0 + 3600, sleep_fn=lambda s: None,
           disk_fn=lambda p: Disk(0, 0, 40e9), tracked_fn=lambda r, d: set(), out=lambda m: None)
    back = r.check(T0 + 3600 + R.CHECK_EVERY_S)
    assert len(back) == 1 and "working again" in back[0][0] and "moved 1 file(s)" in back[0][0], back
    assert os.path.exists(os.path.join(TMP, "archive", "pinrun-paper-20261001T000000Z.jsonl.gz"))


def test_the_monitor_runs_it():
    assert ("rotation", M.check_rotation) in M.CHECKS
    clear()
    status(git="unreadable")
    st = types.SimpleNamespace()
    sent = []
    ctx = types.SimpleNamespace(now=lambda: T0)
    saved = M.CHECKS

    def planted(*a):
        raise RuntimeError("planted: a check before it fails")
    # the other checks need a full phone; here they are no-ops, and one before rotation fails (it cannot stop it)
    M.CHECKS = tuple((n, f if n == "rotation" else (planted if n == "alive" else (lambda *a: None))) for n, f in saved)
    try:
        M.tick(ctx, st, lambda msg, urgent=False: sent.append(str(msg)), T0)
    finally:
        M.CHECKS = saved
    assert len(sent) == 1 and "moved nothing" in sent[0], sent


def test_server_page_line():
    clear()
    now = T0
    status()
    h = R.health(now)
    lines = R.server_lines(h, now)
    assert lines[0] == ("🗜 <b>Log rotation</b>: last run 4:20 AM ET (1 h 59 min ago): moved 12 file(s), 1,234 MB "
                        "packed to 98 MB, freed 1,136 MB"), lines
    assert lines[1] == ("<i>Disk: 25.7 GB free, filling about 1.14 GB a week: about 17 weeks to the 6 GB line "
                        "(measured over the last 9 days of runs).</i>"), lines
    status(git="unreadable")
    bad = R.server_lines(R.health(now), now)
    assert bad[0].startswith("⚠️ <b>Log rotation moved nothing</b> · the alert said why"), bad
    clear()
    put(LR.INSTALLED_NAME, {"installed_t": now - 3600})
    w = R.server_lines(R.health(now), now)
    assert w == ["🗜 <b>Log rotation</b>: installed 5:20 AM ET; its first run is Nov 8 4:40 AM ET (then daily)"], w
    for ls in (lines, bad, w):
        assert tg_html_problems("\n".join(ls)) == [], ls
    # the page: the section sits under the machine; without it the page is exactly what it was
    args = (MACH, {"ms": [4.1, 5.2, 6.3], "dns_ms": 1.2, "ip": "1.2.3.4", "err": None, "t": now},
            {"pots": {"0": {"value": 1246.86, "open": 12.30, "cash": 1234.56, "why": None, "t": now - 600}},
             "total": 1246.86, "t": now - 600}, {}, PG.aws_estimate(now), now)
    base = str(PG.server_html(*args))
    assert str(PG.server_html(*args, rotation=None)) == base
    assert str(PG.server_html(*args, rotation={"state": "none", "bad": False})) == base
    withr = str(PG.server_html(*args, rotation=h))
    assert "🗜 <b>Log rotation</b>" not in base and lines[0] in withr and tg_html_problems(withr) == []
    assert withr.index("Last boot:") < withr.index(lines[0]) < withr.index("⚡ <b>Kalshi"), "under the machine"


def main():
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    t0 = time.time()
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print("  ok   %s" % name, flush=True)
        except Exception:                                       # noqa: BLE001
            failed.append(name)
            print("  FAIL %s\n%s" % (name, traceback.format_exc()), flush=True)
    print("test_rotation: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
