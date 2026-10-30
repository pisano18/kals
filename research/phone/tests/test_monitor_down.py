"""test_monitor_down.py -- phone/monitor.py's DOWN watch (v-tg-rebuild step 12, lane Q): the warning line on /status and
/bots, the DOWN alert's debounce (more than 2 checks AND 3 min; telegram.json "down_alert_s"), once per episode, 'back up'
and 'paused now', a normal restart that never alerts, muted, and the runtime switch (Phone.monitor_on).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_monitor_down.py   (exit 0 = every test passed)
A fake clock, a planted process table and a temp results folder (stop files, log mtimes). KALS_TESTING=1; no network.
"""
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

import bots                                                          # noqa: E402
from botdata import paths, status                                    # noqa: E402
from phone import alerts as A                                        # noqa: E402
from phone import monitor as M                                       # noqa: E402
from phone import log as plog                                        # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_monitor_down_")
paths.set_results(TMP)
plog.set_path(lambda: os.path.join(TMP, "pinphone.log"), replace=True)
T0 = 1793370120.0               # 2026-10-30 14:22Z = 10:22 AM ET
LIVE = {b.name: [1000 + i, "", "python.exe -u %s --live" % b.script] for i, b in enumerate(bots.all_bots())}


def table(*running):
    return [LIVE[n] for n in running]


def stop(name, on=True):
    p = os.path.join(TMP, bots.get(name).stop_file)
    if on:
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("test\n")
    elif os.path.exists(p):
        os.remove(p)


def log_at(name, t):
    p = os.path.join(TMP, bots.get(name).logs.path)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("{}\n")
    os.utime(p, (t, t))


def setup():
    """Every bot but the jump band and the ladder paused (stop file) -- those two run unless a test says otherwise."""
    for b in bots.all_bots():
        stop(b.name, b.name not in ("jumpband", "ladder"))
    log_at("jumpband", T0 - 20 * 60)                      # 10:02 AM ET


class Rig:
    def __init__(self, cfg=None):
        self.now = T0
        self.rows = table("jumpband", "ladder")
        self.sent = []
        self.st = types.SimpleNamespace()
        self.ctx = FakeCtx(now=None, now_fn=lambda: self.now, bs_procs=None, cfg=cfg or {}, pots={"pots": {}},
                           bs_getter=lambda path, params: (599, "tests: no Kalshi"))

    def tick(self, dt, rows=None):
        self.now = T0 + dt
        if rows is not None:
            self.rows = rows
        self.ctx.bs_procs = list(self.rows)
        before = len(self.sent)
        M.tick(self.ctx, self.st, lambda msg, urgent=False: self.sent.append((str(msg), urgent)))
        return self.sent[before:]


def test_down_line_on_the_pages():
    setup()
    r = Rig()
    r.ctx.bs_procs = table("ladder")
    lines = M.down_lines(r.ctx)
    assert lines == ["⚠️ <b>Jump band is not running and was not paused</b> (last log 10:02 AM)", ""], lines
    r.ctx.bs_procs = table("ladder", "jumpband")
    assert M.down_lines(r.ctx) == []
    stop("jumpband")                                       # paused: never a warning
    r.ctx.bs_procs = table("ladder")
    assert M.down_lines(r.ctx) == []
    stop("jumpband", False)
    r.ctx.bs_procs = lambda: None                          # unreadable table: UNKNOWN, no line
    assert M.down_lines(r.ctx) == []
    log_at("jumpband", T0 - 86400)                         # an older day says the day
    r.ctx.bs_procs = table("ladder")
    assert "(last log Oct 29 10:22 AM)" in M.down_lines(r.ctx)[0], M.down_lines(r.ctx)
    os.remove(os.path.join(TMP, "jumpband-live.jsonl"))
    assert "(no log yet)" in M.down_lines(r.ctx)[0]


def test_debounce_then_once_then_back():
    setup()
    r = Rig()
    assert r.tick(0) == []
    gone = table("ladder")
    assert r.tick(30, gone) == []                          # check 1
    assert r.tick(60) == []                                # check 2
    assert r.tick(150) == []                               # check 3 but 2 min: under 3 min
    got = r.tick(215)                                      # check 4, 3 min 05 s since first seen
    assert len(got) == 1 and got[0][1] is True, got
    msg = got[0][0]
    assert msg.startswith("🚨 <b>Jump band is DOWN</b>: not running, and it was not paused (no stop file)"), msg
    assert "it makes $0 until it runs again" in msg and "no keep-alive" in msg and "Seen down for 3 min" in msg, msg
    assert "its log last moved 10:02 AM ET" in msg, msg
    assert r.tick(260) == [] and r.tick(900) == []         # once per episode
    back = r.tick(960, table("jumpband", "ladder"))
    assert len(back) == 1 and back[0][1] is True
    assert back[0][0] == "✅ <b>Jump band is back up</b> -- running again after about 15 min down (from 10:22 AM to " \
                        "10:38 AM ET).", back
    assert r.tick(1000) == []


def test_a_normal_restart_never_alerts():
    setup()
    r = Rig()
    r.tick(0)
    gone = table("ladder")
    for dt in (30, 60, 90, 120, 150, 170):                 # 6 checks inside 3 min: still under the debounce
        assert r.tick(dt, gone) == []
    assert r.tick(175, table("jumpband", "ladder")) == []  # back before the alert: nothing, ever
    assert r.tick(400) == [] and M.state_of(r.st).down == {}


def test_more_than_two_checks_are_needed_too():
    setup()
    r = Rig()
    r.tick(0)
    gone = table("ladder")
    assert r.tick(10, gone) == []
    assert r.tick(400) == []                               # 2 checks, 6 min: not yet (more than 2 checks)
    assert len(r.tick(430)) == 1


def test_configurable_and_keepalive_words():
    setup()
    r = Rig(cfg={"down_alert_s": 60})
    r.tick(0)
    gone = table("jumpband")                               # the ladder (boot_all keep-alive) goes down
    r.tick(10, gone)
    r.tick(40)
    got = r.tick(75)
    assert len(got) == 1 and got[0][0].startswith("🚨 <b>Ladder is DOWN</b>"), got
    assert "Its keep-alive: boot_all.ps1 (every 10 min) restarts it" in got[0][0]


def test_paused_instead_of_back():
    setup()
    r = Rig()
    r.tick(0)
    gone = table("ladder")
    for dt in (30, 60, 120, 215):
        r.tick(dt, gone)
    assert any("DOWN" in m for m, _u in r.sent)
    stop("jumpband")
    got = r.tick(260)
    assert got == [("⏸ <b>Jump band was down and is paused now</b> (its stop file is set): no more alerts about it "
                    "until it runs again.", True)], got
    stop("jumpband", False)


def test_unreadable_table_changes_nothing():
    setup()
    r = Rig()
    r.tick(0)
    r.tick(30, table("ladder"))
    r.ctx.bs_procs = None
    r.rows = []
    st = M.state_of(r.st)
    n = st.down["jumpband"]["checks"]
    r.now = T0 + 500
    r.ctx.bs_procs = lambda: None
    M.tick(r.ctx, r.st, lambda msg, urgent=False: r.sent.append(msg))
    assert st.down["jumpband"]["checks"] == n and not r.sent


def test_through_the_alerts_tick_switch_and_mute():
    """alerts.tick runs the monitor only when the runtime says monitor_on; muted, it learns but sends nothing."""
    setup()
    from phone.app import Phone
    from phone.transport import FakeTelegram

    class Led:
        results = TMP

        def refresh(self):
            pass

        def losing_closes(self):
            return []

    now = {"t": T0}
    h = {"pid": 1, "alive": True, "flag": None, "quiet_s": 5, "watchdog_s": 5, "open": {}, "halt": None,
         "kalshi_ok": True, "feeds_ok": True, "disk_gb": 30.0}
    ph = Phone({"chat_id": 7}, FakeTelegram(), ledger=Led(), health_fn=lambda: h, now_fn=lambda: now["t"])
    ph.last_daily = "2099-01-01"
    ph.bs_procs = table("ladder")
    assert ph.monitor_on is False
    for dt in (0, 30, 60, 200):
        now["t"] = T0 + dt
        ph.alerts_tick()
    assert ph.tg.sent == [] and getattr(ph, "monitor", None) is None     # off: never ran
    ph.monitor_on, ph.muted = True, True
    for dt in (300, 330, 360, 600):
        now["t"] = T0 + dt
        ph.alerts_tick()
    assert ph.tg.sent == [] and ph.monitor.down["jumpband"]["sent"] is True   # muted: learnt, not sent
    ph.muted = False
    ph.bs_procs = table("ladder", "jumpband")
    now["t"] = T0 + 700
    sent = ph.alerts_tick()
    assert len(sent) == 1 and "back up" in str(sent[0]) and len(ph.tg.sent) == 1


def test_status_and_bots_put_the_line_first():
    import phone.commands.bots_page as BP
    saved = M.down_lines, BP.bs_all_html
    try:
        M.down_lines = lambda ctx: ["⚠️ warn", ""]
        BP.bs_all_html = lambda a: ["page"]
        assert str(BP.render({}, None)) == "⚠️ warn\n\npage"
    finally:
        M.down_lines, BP.bs_all_html = saved
    import phone.commands.status as SC
    src = open(SC.__file__, encoding="utf-8").read()
    assert "down = _monitor.down_lines(ctx)" in src and 'list(d.get("down") or []) + [' in src


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
    print("test_monitor_down: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
