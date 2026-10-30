"""test_quiet.py -- quiet hours (v-tg-rebuild step 12, lane Q): phone/quiet.py's rule (the hours, the ET wall clock across
the clock change, /quiet's argument, the urgent loss), phone/alerts.py's holding (only with the monitor on; urgent alerts
go; the rest wait and come as ONE summary when quiet hours end; muted drops them) and /quiet (shown, set, off, on, bad;
saved in the phone's config file).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_quiet.py   (exit 0 = every test passed)
A fake clock, FakeTelegram, a temp config file. KALS_TESTING=1; no network.
"""
import calendar
import json
import os
import sys
import tempfile
import time
import traceback

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import bots                                                          # noqa: E402
from botdata import paths                                            # noqa: E402
from phone import alerts as A                                        # noqa: E402
from phone import log as plog                                        # noqa: E402
from phone import monitor as M                                       # noqa: E402
from phone import quiet as Q                                         # noqa: E402
from phone.commands import quiet_cmd as QC                           # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402
from phone.html import Html                                          # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_quiet_")
paths.set_results(TMP)
plog.set_path(lambda: os.path.join(TMP, "pinphone.log"), replace=True)
for _b in bots.all_bots():                       # every bot paused: the DOWN watch says nothing here
    with open(os.path.join(TMP, _b.stop_file), "w", encoding="utf-8") as _fh:
        _fh.write("x")


def et(y, mo, d, h, mi=0):
    """ET wall clock -> epoch (EDT until 2026-11-01 06:00Z, EST after)."""
    t = calendar.timegm((y, mo, d, h, mi, 0))
    return t + (4 if t + 4 * 3600 < calendar.timegm((2026, 11, 1, 6, 0, 0)) else 5) * 3600


def test_the_rule():
    assert Q.hours({}) == (23, 7) and Q.words({}) == "11 PM to 7 AM ET"
    assert Q.hours({"quiet_hours": "off"}) is None and Q.words({"quiet_hours": "off"}) == "off"
    assert Q.hours({"quiet_hours": [22, 6]}) == (22, 6) and Q.hours({"quiet_hours": "junk"}) == (23, 7)
    assert Q.hours({"quiet_hours": [5, 5]}) == (23, 7) and Q.words({"quiet_hours": [0, 12]}) == "12 AM to 12 PM ET"
    night = {}
    assert [Q.is_quiet(night, et(2026, 10, 30, h, 30)) for h in (22, 23, 0, 3, 6, 7, 12)] == \
        [False, True, True, True, True, False, False]
    day = {"quiet_hours": [9, 17]}
    assert [Q.is_quiet(day, et(2026, 10, 30, h)) for h in (8, 9, 16, 17)] == [False, True, True, False]
    assert not Q.is_quiet({"quiet_hours": "off"}, et(2026, 10, 30, 2))
    assert Q.is_quiet(night, et(2026, 11, 1, 6, 59)) and not Q.is_quiet(night, et(2026, 11, 1, 7, 0))  # after the change
    assert Q.parse("") == ("show",) and Q.parse(" OFF ") == ("off",) and Q.parse("on") == ("on",)
    assert Q.parse("23-7") == ("set", (23, 7)) and Q.parse("22:00 - 6:00") == ("set", (22, 6))
    assert Q.parse("22 to 6") == ("set", (22, 6))
    assert Q.parse("25-7")[0] == Q.parse("7-7")[0] == Q.parse("late")[0] == "bad"
    assert Q.loss_is_urgent(-50.0, None) and not Q.loss_is_urgent(-49.99, None)
    assert Q.loss_is_urgent(-31.0, 1000.0) and not Q.loss_is_urgent(-29.0, 1000.0) and not Q.loss_is_urgent(5.0, 10.0)


class Led:
    results = TMP

    def refresh(self):
        pass

    def losing_closes(self):
        return []


def _phone(now, h):
    from phone.app import Phone
    from phone.transport import FakeTelegram
    ph = Phone({"chat_id": 7}, FakeTelegram(), ledger=Led(), health_fn=lambda: h, now_fn=lambda: now["t"],
               cfg_path=os.path.join(TMP, "telegram.json"))
    ph.last_daily = "2099-01-01"                 # no 8 AM summary in these scripts
    ph.bs_procs = []
    ph.bs_getter = lambda path, params: (599, "tests: no Kalshi")
    return ph


H0 = {"pid": 1, "alive": True, "flag": None, "quiet_s": 5, "watchdog_s": 5, "open": {}, "halt": None,
      "kalshi_ok": True, "feeds_ok": True, "disk_gb": 30.0}


def test_held_overnight_then_one_summary():
    now, h = {"t": et(2026, 10, 30, 22, 0)}, dict(H0)
    ph = _phone(now, h)
    ph.monitor_on = True
    ph.alerts_tick()                                         # learns
    now["t"] = et(2026, 10, 31, 2, 10)
    h["disk_gb"] = 7.5                                       # low disk: not urgent -> held
    assert ph.alerts_tick() == [] and ph.tg.sent == []
    h["kalshi_ok"] = False                                   # a recorder silent: held too
    now["t"] = et(2026, 10, 31, 2, 20)
    assert ph.alerts_tick() == []
    h["alive"], h["pid"] = False, None                       # the pin bot stops: its state change is urgent
    now["t"] = et(2026, 10, 31, 3, 0)
    got = ph.alerts_tick()
    assert len(got) == 1 and "STATE CHANGED" in str(got[0]) and len(ph.tg.sent) == 1
    assert len(ph.monitor.held) == 2
    now["t"] = et(2026, 10, 31, 6, 59)
    assert ph.alerts_tick() == []
    now["t"] = et(2026, 10, 31, 7, 1)                        # quiet hours over: ONE summary of the two
    got = ph.alerts_tick()
    assert len(got) == 1 and ph.monitor.held == [], got
    s = str(got[0])
    assert s.startswith("🌅 <b>Quiet hours are over: 2 alerts held</b> (11 PM to 7 AM ET; only urgent ones came then)")
    assert "<i>— held at 2:10 AM ET —</i>\n⚠️ <b>DISK 7.5 GB free, under 8 GB.</b>" in s, s
    assert "<i>— held at 2:20 AM ET —</i>\n⚠️ <b>RECORDER SILENT: Kalshi recorder</b>" in s, s
    assert ph.alerts_tick() == []


def test_off_muted_and_the_monitor_switch():
    now, h = {"t": et(2026, 10, 30, 22, 0)}, dict(H0)
    ph = _phone(now, h)
    ph.alerts_tick()
    now["t"], h["disk_gb"] = et(2026, 10, 31, 2, 10), 7.5
    got = ph.alerts_tick()                                   # monitor off: exactly as before, sent at once
    assert len(got) == 1 and "DISK" in str(got[0])
    ph2 = _phone(now, dict(H0))
    ph2.monitor_on, ph2.cfg["quiet_hours"] = True, "off"
    ph2.alerts_tick()
    ph2.health_fn = lambda: dict(H0, disk_gb=7.5)
    assert len(ph2.alerts_tick()) == 1                       # quiet hours off: sent
    ph3 = _phone(now, dict(H0))
    ph3.monitor_on = True
    ph3.alerts_tick()
    ph3.health_fn = lambda: dict(H0, disk_gb=7.5)
    ph3.alerts_tick()
    assert len(ph3.monitor.held) == 1
    ph3.muted = True                                         # muted when they end: dropped, nothing sent
    now["t"] = et(2026, 10, 31, 8, 0)
    assert ph3.alerts_tick() == [] and ph3.monitor.held == [] and ph3.tg.sent == []


def test_urgent_loss_through_the_sender():
    sent, st = [], type("S", (), {})()
    ctx = FakeCtx(now=0, cfg={}, say=lambda m, chat_id=None: None)
    ctx.state = type("R", (), {"muted": False, "monitor_on": True})()
    send = A.sender(ctx, sent, st, et(2026, 10, 31, 2, 0))
    asked = []
    assert send("small", urgent=lambda: asked.append(1) or Q.loss_is_urgent(-10.0, 1000.0)) is False and asked
    assert send("big", urgent=lambda: Q.loss_is_urgent(-60.0, None)) is True and sent == ["big"]
    assert [m for _t, m in M.state_of(st).held] == ["small"]
    day = A.sender(ctx, sent, st, et(2026, 10, 31, 12, 0))
    asked[:] = []
    assert day("noon", urgent=lambda: asked.append(1)) is True and not asked     # not quiet: never asked


def test_the_quiet_command():
    cfgp = os.path.join(TMP, "telegram_cmd.json")
    cfg = {"chat_id": 7, "secret": "s"}

    def run(text, now=et(2026, 10, 31, 2, 0), held=0):
        ctx = FakeCtx(text=text, now=now, cfg=cfg, cfg_path=cfgp)
        ctx.state = type("R", (), {"muted": False, "monitor": M.MonitorState(held=[(0, "x")] * held)})()
        return QC.COMMAND.run(ctx)
    r = run("/quiet", held=2)
    assert isinstance(r, Html) and str(r).startswith("🌙 <b>Quiet hours: 11 PM to 7 AM ET</b>\nFrom 11 PM to 7 AM ET only "
                                                     "urgent alerts come: a bot DOWN"), str(r)
    assert "Now: <b>quiet</b> · 2 alerts held." in str(r) and not os.path.exists(cfgp)
    r = run("/quiet 22-6", now=et(2026, 10, 31, 12, 0))
    assert str(r).startswith("🌙 <b>Quiet hours now 10 PM to 6 AM ET</b>") and "Now: <b>not quiet</b>." in str(r)
    with open(cfgp, encoding="utf-8") as fh:
        assert json.load(fh) == {"chat_id": 7, "secret": "s", "quiet_hours": [22, 6]}
    assert str(run("/quiet off")).startswith("🌙 <b>Quiet hours off</b>\nEvery alert comes at any hour.")
    with open(cfgp, encoding="utf-8") as fh:
        assert json.load(fh)["quiet_hours"] == "off"
    assert "now 11 PM to 7 AM ET" in str(run("/quiet on"))
    assert str(run("/quiet 25-7")) == "🌙 I did not change the quiet hours: an hour is 0 to 23 (ET): /quiet 23-7."
    assert cfg["quiet_hours"] == [23, 7]
    assert QC.COMMAND.section == "controls" and QC.COMMAND.kind_of("/quiet") is None and not QC.COMMAND.needs_ledger


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
    print("test_quiet: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
