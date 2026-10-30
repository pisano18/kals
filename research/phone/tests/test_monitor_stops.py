"""test_monitor_stops.py -- the early warnings before a stop trips (v-tg-rebuild step 12, lane Q): each bot's Bot.stop_gauges
hook on its own records (the pin bot's loss abort, the jump band's stop line and day stop, the FX taker's stop line and day
stop, the ladder's day-stop rail), botdata/watch.py's levels, and phone/monitor.py's check: the first read learns, once
per level per period, the trip is urgent, a new day re-arms, the reads are throttled, a broken hook costs only its bot.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_monitor_stops.py   (exit 0 = every test passed)
A fake clock and a temp results folder holding hand-written logs. KALS_TESTING=1; no network.
"""
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

import bots                                                          # noqa: E402
from botdata import paths, watch                                     # noqa: E402
from phone import log as plog                                        # noqa: E402
from phone import monitor as M                                       # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_monitor_stops_")
paths.set_results(TMP)
plog.set_path(lambda: os.path.join(TMP, "pinphone.log"), replace=True)
T0 = 1793370120.0               # 2026-10-30 14:22Z = 10:22 AM ET
LIVE = {b.name: [1000 + i, "", "python.exe -u %s --live" % b.script] for i, b in enumerate(bots.all_bots())}


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def write(name, recs, mode="w"):
    with open(os.path.join(TMP, name), mode, encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


def jb(line_money, day_money, dt, kind="settle"):
    write("jumpband-live.jsonl", [{"t": iso(T0 + dt), "kind": kind, "line_money": line_money, "day_money": day_money}],
          "a")


def fresh_logs():
    for f in os.listdir(TMP):
        if f.endswith(".jsonl") or f.endswith(".stop"):
            os.remove(os.path.join(TMP, f))
    write("jumpband-live.jsonl", [
        {"t": iso(T0 - 3600), "kind": "start", "live": False, "stop_line": -99.0},           # a paper start: not it
        {"t": iso(T0 - 1800), "kind": "start", "live": True, "stop_line": -25.0, "day_stop": -15.0, "line_money": -2.0},
        {"t": iso(T0 - 600), "kind": "health", "line_money": -3.0, "day_money": -1.0}])
    write("pinrun-live-20261028T011720Z.jsonl", [
        {"t": iso(T0 - 7200), "kind": "start", "loss_abort": -200.0},
        {"t": iso(T0 - 3600), "kind": "autosize", "loss_abort": -250.0, "why": "bank $1300.00"},
        {"t": iso(T0 - 600), "kind": "settled", "realised": 40.0, "day_realised": -20.0}])
    write("fxtake-live-orders.jsonl", [
        {"t": iso(T0 - 3600), "kind": "start", "stop_line": -10.0, "stop_line_since": "2026-10-26T06:20:27Z",
         "line_pnl": 4.0, "day_stop": -25.0},
        {"t": iso(T0 - 600), "kind": "settle", "run_pnl": -2.0, "day_pnl": -2.0}])
    write("ladder-live-orders.jsonl", [
        {"t": iso(T0 - 9000), "ev": "start", "rails": {"day_stop": -100.0}},
        {"t": iso(T0 - 3600), "ev": "rescale", "rails": {"day_stop": -150.0}},
        {"t": iso(T0 - 600), "ev": "live_settle", "day_pnl": -10.0}])
    for b in bots.all_bots():                     # only the four with stops run
        if b.name not in ("pin", "jumpband", "fx", "ladder"):
            write(b.stop_file, [{}])


class Rig:
    def __init__(self):
        self.now = T0
        self.sent = []
        self.st = types.SimpleNamespace()
        self.ctx = FakeCtx(now_fn=lambda: self.now, bs_procs=[LIVE[n] for n in ("pin", "jumpband", "fx", "ladder")],
                           cfg={}, pots={"pots": {"3": {"value": 50.0}, "0": {"value": 1300.0}}})

    def tick(self, dt):
        self.now = T0 + dt
        before = len(self.sent)
        M.tick(self.ctx, self.st, lambda msg, urgent=False: self.sent.append((str(msg), urgent)))
        return self.sent[before:]


def test_every_hook_reads_its_own_records():
    fresh_logs()
    g = {(n, x.key): x for n in ("pin", "jumpband", "fx", "ladder", "race") for x in watch.gauges(n, T0)}
    assert sorted(g) == [("fx", "day"), ("fx", "line"), ("jumpband", "day"), ("jumpband", "line"), ("ladder", "day"),
                         ("pin", "abort")], sorted(g)
    p = g[("pin", "abort")]
    assert (p.money, p.line, p.warn_at, p.counted) == (-20.0, -250.0, (-150.0, -200.0), "settled today"), p
    assert p.period == "2026-10-30 run 20261028T011720Z"
    j, jd = g[("jumpband", "line")], g[("jumpband", "day")]
    assert (j.money, j.line, j.warn_at, j.period) == (-3.0, -25.0, (-15.0, -20.0), "live"), j
    assert (jd.money, jd.line, jd.warn_at, jd.period) == (-1.0, -15.0, (-10.0,), "2026-10-30"), jd
    f, fd = g[("fx", "line")], g[("fx", "day")]
    assert (f.money, f.line, f.warn_at) == (2.0, -10.0, (-5.0, -7.5)), f      # line_pnl 4 + run -2
    assert (fd.money, fd.warn_at) == (-2.0, (-15.0, -20.0)), fd
    lad = g[("ladder", "day")]
    assert (lad.money, lad.line, lad.warn_at) == (-10.0, -150.0, (-90.0, -120.0)), lad
    assert all(watch.gauge_level(x) == 0 for x in g.values())


def test_levels():
    G = bots.spec.Gauge
    g = lambda money, tripped=False: G("k", "w", money, -25.0, (-15.0, -20.0), "p", tripped=tripped)  # noqa: E731
    assert [watch.gauge_level(g(m)) for m in (0.0, -15.0, -19.99, -20.0, -24.99, -25.0, -40.0)] == [0, 1, 1, 2, 2, 3, 3]
    assert watch.gauge_level(g(5.0, tripped=True)) == 3


def test_learn_then_once_per_level_then_trip():
    fresh_logs()
    jb(-16.0, -4.0, -100)                          # already past the first line level when the phone starts
    r = Rig()
    assert r.tick(0) == []                          # learns: nothing said
    assert r.tick(30) == []
    jb(-17.0, -10.5, 10)
    got = r.tick(61)                                # day stop: $5 from it
    assert len(got) == 1 and got[0][1] is False, got
    assert got[0][0] == ("⚠️ <b>Jump band -$10.50 settled today: $4.50 from its day stop (-$15.00)</b> · <b>-21.00%</b> "
                         "of its pot\n70% of the way there. At -$15.00 it stops for the rest of the day and starts "
                         "again by itself tomorrow. Next: the stop itself."), got
    jb(-20.5, -11.0, 70)
    got = r.tick(125)                               # the stop line: $5 from it (level 2)
    assert len(got) == 1 and "-$20.50 settled since it went live: $4.50 from its stop line (-$25.00)" in got[0][0]
    assert "Next: the stop itself." in got[0][0] and got[0][1] is False
    jb(-19.0, -9.0, 130)                            # back up a little: nothing re-arms inside the period
    assert r.tick(190) == []
    jb(-26.0, -16.0, 200)
    got = r.tick(260)                               # both trip at once: two urgent alerts
    assert [u for _m, u in got] == [True, True], got
    assert got[0][0] == ("🛑 <b>Jump band hit its stop line (-$25.00)</b>: -$26.00 settled since it went live · "
                         "<b>-52.00%</b> of its pot.\nIt stands down for good (it writes its stop file; nothing "
                         "restarts it)."), got
    assert got[1][0].startswith("🛑 <b>Jump band hit its day stop (-$15.00)</b>: -$16.00 settled today")
    assert r.tick(400) == []


def test_pin_at_60_and_80_percent():
    fresh_logs()
    r = Rig()
    r.tick(0)
    write("pinrun-live-20261028T011720Z.jsonl", [{"t": iso(T0 + 10), "kind": "settled", "realised": -10.0,
                                                    "day_realised": -151.0}], "a")
    got = r.tick(61)
    assert len(got) == 1 and got[0][0].startswith(
        "⚠️ <b>Pin bot -$151.00 settled today: $99.00 from its loss abort (-$250.00)</b> · <b>-11.62%</b> of its pot"
        "\n60% of the way there. At -$250.00 it halts: no new bets until /start. Next warning at -$200.00."), got
    write("pinrun-live-20261028T011720Z.jsonl", [{"t": iso(T0 + 70), "kind": "settled", "realised": -205.0,
                                                    "day_realised": -170.0}], "a")
    got = r.tick(122)                               # the run's loss is the worse one now
    assert len(got) == 1 and "-$205.00 settled this run" in got[0][0] and "Next: the stop itself." in got[0][0], got
    write("pinrun-live-20261028T011720Z.jsonl", [{"t": iso(T0 + 130), "kind": "halt",
                                                    "why": "loss abort: realised $-251.00 <= $-250.00"}], "a")
    got = r.tick(183)
    assert len(got) == 1 and got[0][1] is True and got[0][0].startswith("🛑 <b>Pin bot hit its loss abort (-$250.00)")


def test_a_new_day_rearms_and_reads_are_throttled():
    fresh_logs()
    r = Rig()
    r.tick(0)
    write("fxtake-live-orders.jsonl", [{"t": iso(T0 + 5), "kind": "settle", "run_pnl": -10.5, "day_pnl": -16.0}], "a")
    assert r.tick(30) == []                         # inside GAUGE_EVERY_S: not read yet
    got = r.tick(60)
    texts = [m for m, _u in got]
    assert len(got) == 2 and any("its day stop (-$25.00)" in m for m in texts), texts      # day at 60%
    assert any("-$6.50 settled since 2026-10-26: $3.50 from its stop line" in m for m in texts), texts
    nd = 86400
    write("fxtake-live-orders.jsonl", [{"t": iso(T0 + nd), "kind": "settle", "run_pnl": -11.0, "day_pnl": -16.0}], "a")
    got = r.tick(nd + 10)                           # tomorrow: the day stop warns again; the line does not
    assert len(got) == 1 and "its day stop" in got[0][0], got


def test_paused_bots_and_broken_hooks():
    fresh_logs()
    r = Rig()
    r.tick(0)
    write("jumpband-live.stop", [{}])               # paused: never read
    jb(-30.0, -20.0, 10)
    saved = bots.get("ladder").stop_gauges
    object.__setattr__(bots.get("ladder"), "stop_gauges", lambda wi: 1 / 0)
    try:
        write("pinrun-live-20261028T011720Z.jsonl", [{"t": iso(T0 + 10), "kind": "settled", "realised": -10.0,
                                                        "day_realised": -160.0}], "a")
        got = r.tick(61)
    finally:
        object.__setattr__(bots.get("ladder"), "stop_gauges", saved)
        os.remove(os.path.join(TMP, "jumpband-live.stop"))
    assert len(got) == 1 and got[0][0].startswith("⚠️ <b>Pin bot"), got


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
    print("test_monitor_stops: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
