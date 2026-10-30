"""test_alerts.py -- phone/alerts.py: AlertState + tick, disk_alert, the alert_* layouts, fmt_or_plain, daily_alert, each
against pinphone's own (Phone.alerts_tick, Phone.daily_alert, pinphone.disk_alert / alert_*), on planted health and a
planted ledger.

v-tg-rebuild step 9 (2026-10-30, lane E). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_alerts.py
The golden scripts (tick/alerts-*) on real fixture data are research/golden/shadow_more.py. KALS_TESTING=1; no network.
"""
import calendar
import copy
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

import pinphone as pp                                                # noqa: E402
from phone import alerts as A                                       # noqa: E402
from phone.context import Ctx                                        # noqa: E402
from phone.html import Html                                          # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_alerts_")
pp.LOG = os.path.join(TMP, "pinphone.log")
H0 = {"pid": 4242, "alive": True, "flag": None, "quiet_s": 12, "watchdog_s": 5, "open": {}, "halt": None,
      "kalshi_ok": True, "feeds_ok": True, "disk_gb": 30.0}
C2 = "KXBTC15M-26SEP161015-15"


class FakeLedger:
    results = TMP

    def __init__(self):
        self.losses = []

    def refresh(self):
        pass

    def losing_closes(self):
        return list(self.losses)

    def bank_at(self, t):
        return 500.0

    def contracts_for(self, tk):
        return 40.0 if tk == C2 else 0


def _sent(tg):
    return [(cid, type(m).__name__, str(m)) for cid, m in tg.sent]


def _view(x):
    return [(type(m).__name__, str(m)) for m in x]


class Pair:
    """The old Phone and the new tick side by side on the same health, ledger and clock."""

    def __init__(self, now):
        self.h = dict(H0)
        self.led = FakeLedger()
        self.now = now
        mk = lambda: pp.Phone({"chat_id": 111}, pp.FakeTelegram(), ledger=self.led, health_fn=lambda: self.h,
                              now_fn=lambda: self.now["t"])
        self.old, self.new = mk(), mk()
        self.st = A.AlertState()

    def set_muted(self, m):
        self.old.muted = self.new.muted = m

    def tick(self, why):
        a = self.old.alerts_tick()
        b = A.tick(Ctx.from_phone(self.new), self.st)
        assert _view(a) == _view(b), (why, _view(a), _view(b))
        assert _sent(self.old.tg) == _sent(self.new.tg), why
        so = (self.old.last_state, self.old.last_rec, self.old.seen_losses, self.old.last_daily, self.old.disk_level)
        sn = (self.st.last_state, self.st.last_rec, self.st.seen_losses, self.st.last_daily, self.st.disk_level)
        assert so == sn, (why, so, sn)
        return b


def _daily_stub(ctx_or_self, d, now, *_a):
    return Html("☀️ <b>DAILY</b> %s" % d)


def test_tick_script_vs_phone():
    now = {"t": calendar.timegm((2026, 9, 16, 15, 0, 0))}             # 11 AM ET Sep 16
    p = Pair(now)
    p.old.daily_alert = lambda d, n: _daily_stub(None, d, n)
    saved = A.daily_alert
    A.daily_alert = _daily_stub
    try:
        assert p.tick("first: learns") == [] and p.st.last_state == "TRADING" and p.st.last_daily == "2026-09-16"
        assert p.tick("no change") == []
        p.h = dict(p.h, alive=False)
        r = p.tick("down")
        assert len(r) == 1 and str(r[0]).startswith("🔴 <b>STATE CHANGED: TRADING -&gt; DOWN</b>")
        assert p.tick("stays down") == []
        p.h = dict(p.h, alive=True)
        assert len(p.tick("back")) == 1
        p.h = dict(p.h, blind={"since": None, "bad": 12, "why": "it cannot reach Kalshi"})
        assert len(p.tick("blind")) == 1
        p.h = dict(p.h, blind=None)
        p.tick("sees again")
        p.h = dict(p.h, kalshi_ok=False)
        assert "RECORDER SILENT: Kalshi recorder" in str(p.tick("recorder silent")[0])
        p.h = dict(p.h, feeds_ok=False)
        p.tick("both silent")
        p.h = dict(p.h, kalshi_ok=True, feeds_ok=True)
        assert "WRITING AGAIN" in str(p.tick("writing again")[0])
        for gb, n in ((7.5, 1), (7.1, 0), (5.9, 1), (8.5, 0), (9.5, 0), (7.9, 1), (None, 0)):
            p.h = dict(p.h, disk_gb=gb)
            assert len(p.tick("disk %s" % gb)) == n, gb
        p.set_muted(True)
        p.h = dict(p.h, disk_gb=5.0, alive=False)
        assert p.tick("muted: disk and state tracked") == [] and p.st.disk_level == 6 and p.st.last_state == "DOWN"
        p.set_muted(False)
        p.h = dict(p.h, disk_gb=30.0, alive=True)
        p.tick("unmuted, back")
        close = calendar.timegm((2026, 9, 16, 14, 15, 0))
        p.led.losses = [(close, -38.8, [{"tk": C2, "want": "no", "cost": 0.97, "result": "yes", "pnl": -38.8}])]
        r = p.tick("a new losing close")
        assert len(r) == 1 and str(r[0]).startswith("🔴 <b>LOSS -$38.80 (-7.76% of the bank)</b>")
        assert p.tick("once") == []
        c3 = close + 900
        p.led.losses.append((c3, -37.0, [
            {"tk": C2, "want": "no", "cost": 0.97, "result": "yes", "pnl": -38.8},
            {"tk": "KXCRYPTOLEAD15M-26SEP161030-SOL", "want": "yes", "cost": 0.9, "result": "yes", "pnl": 1.8, "n": 20.0}]))
        p.led.losses.append((c3 + 900, -1.0, [{"tk": "KXETH15M-26SEP161045-45", "want": "yes", "cost": None,
                                              "result": "no", "pnl": -1.0, "n": "x"}]))
        assert len(p.tick("two new closes, one with both main-account bots' legs")) == 2
        p.set_muted(True)
        p.led.losses.append((c3 + 1800, -2.0, [{"tk": C2, "want": "no", "cost": 0.97, "result": "yes", "pnl": -2.0}]))
        assert p.tick("muted loss: seen, not sent") == []
        p.set_muted(False)
        now["t"] += 86400 - 2 * 3600                                   # 9 AM ET the next day
        r = p.tick("the 8 AM summary")
        assert [str(x) for x in r] == ["☀️ <b>DAILY</b> 2026-09-16"]
        assert p.tick("once a day") == []
    finally:
        A.daily_alert = saved


def test_first_tick_before_8am_leaves_the_summary_due():
    now = {"t": calendar.timegm((2026, 9, 16, 10, 0, 0))}             # 6 AM ET
    p = Pair(now)
    p.old.daily_alert = lambda d, n: _daily_stub(None, d, n)
    saved = A.daily_alert
    A.daily_alert = _daily_stub
    try:
        p.tick("first at 6 AM")
        assert p.st.last_daily is None
        now["t"] += 3 * 3600
        assert len(p.tick("9 AM: due")) == 1
    finally:
        A.daily_alert = saved


def test_unpaired_sends_nothing_and_learns_nothing():
    led = FakeLedger()
    ph = pp.Phone({}, pp.FakeTelegram(), ledger=led, health_fn=lambda: dict(H0), now_fn=lambda: 1.0)
    st = A.AlertState()
    assert A.tick(Ctx.from_phone(ph), st) == [] and st == A.AlertState()


def test_state_defaults_match_the_phone():
    ph = pp.Phone({}, pp.FakeTelegram(), ledger=FakeLedger())
    st = A.AlertState()
    for k in ("last_state", "last_rec", "seen_losses", "last_daily", "disk_level"):
        assert getattr(ph, k) == getattr(st, k), k


def test_st_none_uses_the_phone():
    now = {"t": calendar.timegm((2026, 9, 16, 15, 0, 0))}
    p = Pair(now)
    A.tick(Ctx.from_phone(p.new))
    assert p.new.last_state == "TRADING" and p.new.disk_level == 0 and p.new.seen_losses == set()


def test_a_layout_failure_sends_the_plain_words():
    now = {"t": calendar.timegm((2026, 9, 16, 15, 0, 0))}
    p = Pair(now)
    p.tick("first")
    saved_old, saved_new = pp.alert_state_text, A.alert_state_text
    pp.alert_state_text = lambda *a: 1 / 0
    A.alert_state_text = lambda *a: 1 / 0
    try:
        p.h = dict(p.h, alive=False)
        r = p.tick("layout fails")
        assert len(r) == 1 and type(r[0]) is str and r[0].startswith("STATE CHANGED: TRADING -> DOWN\n")
    finally:
        pp.alert_state_text, A.alert_state_text = saved_old, saved_new
    p.h = dict(p.h, alive=True)
    assert isinstance(p.tick("laid out again")[0], Html)


def test_disk_alert_is_pinphones():
    for level in (0, 6, 8):
        for gb in (None, 30.0, 9.01, 9.0, 8.5, 8.0, 7.99, 7.5, 7.2, 6.0, 5.99, 5.9, 5.5, 5.0, 4.0, 0.0):
            assert A.disk_alert(level, gb) == pp.disk_alert(level, gb), (level, gb)


def test_layouts_are_pinphones():
    for args in (("TRADING", "DOWN", "BOT DOWN", "not running\nChecked: process 1"), ("A<", "B&", "h>", "one line")):
        assert str(A.alert_state_text(*args, pp)) == str(pp.alert_state_text(*args))
    for rec in ("SILENT: Kalshi recorder", "SILENT: a <b>"):
        assert str(A.alert_recorder_text(rec, 10)) == str(pp.alert_recorder_text(rec, 10))
        assert str(A.alert_recorder_back_text(rec)) == str(pp.alert_recorder_back_text(rec))
    for level, gb in ((8, 7.5), (6, 5.9)):
        msg = A.disk_alert(0 if level == 8 else 8, gb)[1]
        assert str(A.disk_alert_html(msg, level)) == str(pp.disk_alert_html(msg, level))
    led = FakeLedger()
    close = calendar.timegm((2026, 9, 16, 14, 15, 0))
    legs = [{"tk": C2, "want": "no", "cost": 0.97, "result": "yes", "pnl": -38.8},
            {"tk": "KXCRYPTOLEAD15M-26SEP161015-SOL", "want": "yes", "cost": 0.9, "result": "yes", "pnl": 1.8, "n": 20.0}]
    for c, lg in ((close, legs), (close, legs[:1]), (close, legs[1:]), (close, [])):
        assert str(A.alert_loss_text(led, c, -37.0, lg, pp)) == str(pp.alert_loss_text(led, c, -37.0, lg))
    assert A.fmt_or_plain(lambda: 1 / 0, lambda: "plain") == "plain"
    assert str(A.fmt_or_plain(lambda: Html("<b>x</b>"), lambda: "plain")) == "<b>x</b>"


def test_daily_alert_vs_phone():
    """Phone.daily_alert's composition: the every-bot block, its fallbacks ('❔' or nothing -> the main-account summary
    alone), the tap with main_words; alert_daily_text planted the same on both sides (the golden tick/alerts-daily
    runs the real one)."""
    saved = pp.alert_daily_text, A.alert_daily_text
    stub = lambda ledger, d, now: Html("☀️ <b>YESTERDAY +$1.00 (+0.20%)</b> · Wed Sep 16\n<b>MONEY:</b> +$1.00")
    pp.alert_daily_text = A.alert_daily_text = stub
    try:
        for top in (["🟢 <b>All bots yesterday</b>", "line <b>2</b>"], [], ["❔ botstats could not be read"]):
            for act in (("pin",), ("pin", "race")):
                ph = pp.Phone({"chat_id": 1}, pp.FakeTelegram(), ledger=FakeLedger(), now_fn=lambda: 1.0)
                ph._all_bots_day = lambda d, title, t=top: list(t)
                ph.active = lambda a=act: a
                c = Ctx.from_phone(ph)
                c.active = ph.active
                old = ph.daily_alert("2026-09-16", 1.0)
                new = A.daily_alert(c, "2026-09-16", 1.0)
                assert type(old) is type(new) and str(old) == str(new), (top, act)
                new2 = A.daily_alert(c, "2026-09-16", 1.0, all_bots_day=lambda d, title, t=top: list(t))
                assert str(new2) == str(old)
    finally:
        pp.alert_daily_text, A.alert_daily_text = saved


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
    print("test_alerts: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
