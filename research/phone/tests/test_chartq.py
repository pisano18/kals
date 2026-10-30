"""test_chartq.py -- phone/chartq.py: the chart queue (2 waiting, the rest dropped, the poll thread never waits), stale
after 120 s, photo retries after 5 s and 20 s, matplotlib missing, nothing to draw / too big, the drawing thread
surviving a failure, and chart_ctx / one() against Phone._chart_ctx / _chart_one.

v-tg-rebuild step 9 (2026-10-30, lane F). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_chartq.py
FakeTelegram (phone.transport) and a fake clock (monotonic + sleep planted); no matplotlib drawing, no network.
"""
import os
import queue
import sys
import tempfile
import threading
import time
import traceback
import types
import urllib.error

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

from _legacy import pp, NEW                                         # noqa: E402  (pp: pinphone_legacy + NEW)
from phone.charts.ctx import as_ctx                                   # noqa: E402
from phone import chartq as Q                                       # noqa: E402
from phone.context import Ctx, FakeCtx                               # noqa: E402
from phone.transport import FakeTelegram                            # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_chartq_")
pp.LOG = os.path.join(TMP, "pinphone.log")
T = 1793448000.0


def log_lines():
    try:
        with open(pp.LOG, encoding="utf-8") as fh:
            return [x.split("  ", 1)[-1] for x in fh.read().splitlines()]
    except FileNotFoundError:
        return []


def clear_log():
    if os.path.exists(pp.LOG):
        os.remove(pp.LOG)


class Clock:
    def __init__(self, t=1000.0):
        self.t = t
        self.slept = []

    def monotonic(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


class FlakyTG(FakeTelegram):
    """send_photo fails `n` times with `err` first."""

    def __init__(self, n=0, err=None):
        super().__init__()
        self.n, self.err = n, err

    def send_photo(self, chat_id, png, caption=None):
        if self.n > 0:
            self.n -= 1
            raise self.err
        super().send_photo(chat_id, png, caption)


TGC = types.SimpleNamespace(kind_of=lambda c: {"/status": "status", "/bars": "bars", "/hedges": "hedges",
                                               "/s": "status"}.get(c),
                            LEDGER_KINDS={"status", "hedges"}, STALE_S=120,
                            build=lambda kind, ctx: (b"PNG-" + kind.encode(), "caption " + kind))
FAKE_PP = types.SimpleNamespace(FUNDS_WHAT={"0": 1, "3": 1}, funds_what=lambda n, act: "%s:%s" % (n, "+".join(act)),
                                _bs=lambda: "botstats", chart_markets=lambda led: {"m": 1},
                                window_stats=lambda ms, taus: {"w": 1}, FIRST_LIVE_DAY="2026-09-08",
                                main_words=lambda act: "words")


def ledger():
    return types.SimpleNamespace(results=TMP, settled=[{"tk": "A"}], orders=[1, 2], hedges=[], autosize=[],
                                 external=[], halts=[], starts=[], closes=[], other="kept")


def state(**kw):
    s = types.SimpleNamespace(charts_on=True, chart_fn=None, chart_stale_s=None, tg=FakeTelegram(), _bars_d={"b": 1})
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def ctx(st, led=None, act=("pin", "fx")):
    return FakeCtx(text="/status", now=T, active=act, pp=FAKE_PP, cfg={"chat_id": 7}, ledger=led or ledger(), state=st,
                   bs_getter="getter", bs_procs="procs")


def cq(st, clock=None, **kw):
    clock = clock or Clock()
    return Q.ChartQueue(st, monotonic=clock.monotonic, sleep=clock.sleep, tgc=lambda: TGC, **kw), clock


def job(kind="status", cmd="/status", queued=1000.0):
    return {"kind": kind, "cmd": cmd, "chat": 7, "queued": queued, "ctx": {"k": kind}}


# ---- after(): the poll thread's side ------------------------------------------------------------------------------------
def test_after_only_paired_drawn_and_on():
    st = state()
    q, _c = cq(st)
    q.q = queue.Queue(maxsize=2)                         # no drawing thread: the jobs stay where the test can see them
    c = ctx(st)
    assert q.after(c, 8, "/status") is False, "another chat"
    assert q.after(c, None, "/status") is False, "no chat"
    assert q.after(c, 7, "/pause") is False and q.after(c, 7, "/stop yes") is False, "no picture for the controls"
    st.charts_on = False
    assert q.after(c, 7, "/status") is False, "charts off"
    assert q.q.qsize() == 0


def test_after_job_and_chart_ctx():
    st = state()
    q, clock = cq(st, Clock(555.0))
    q.q = queue.Queue(maxsize=2)
    led = ledger()
    c = ctx(st, led)
    assert q.after(c, 7, "  /Status@kalsbot now") is True and q.after(c, 7, "/bars") is True
    j1, j2 = q.q.get_nowait(), q.q.get_nowait()
    assert (j1["kind"], j1["cmd"], j1["chat"], j1["queued"]) == ("status", "/status", 7, 555.0)
    x = j1["ctx"]                      # a ChartCtx since v-tg-rebuild step 10 (was the dict with "pp")
    assert (x.now, x.bs_getter, x.bs_procs, x.active) == (T, "getter", "procs", ("pin", "fx"))
    assert (x.botstats, x.markets, x.window_stats, x.first_live_day, x.main_words) == (
        FAKE_PP._bs, FAKE_PP.chart_markets, FAKE_PP.window_stats, "2026-09-08", FAKE_PP.main_words)
    assert x.funds_what == {"0": "0:pin+fx", "3": "3:pin+fx"} and x.bars is None
    assert x.ledger is not led and x.ledger.settled == led.settled and x.ledger.settled is not led.settled
    assert x.ledger.other == "kept"
    led.orders.append(3)
    assert x.ledger.orders == [1, 2], "the snapshot does not see later appends"
    assert j2["kind"] == "bars" and j2["ctx"].bars == {"b": 1} and j2["ctx"].ledger is None


def test_after_never_raises():
    st = state()
    q, _c = cq(st)
    q._tgc = lambda: 1 / 0
    assert q.after(ctx(st), 7, "/status") is False
    assert any("ZeroDivisionError" in x for x in log_lines())


def test_queue_of_two_never_waits():
    """One draws (blocked), two wait, the next is dropped AT ONCE (logged) -- the poll thread never waits; then all
    three that were kept are sent, in order."""
    clear_log()
    drawing, release = threading.Event(), threading.Event()

    def slow(kind, c):
        drawing.set()
        release.wait(10)
        return b"PNG", "cap %s" % c.now
    st = state(chart_fn=slow)
    q = Q.ChartQueue(st, tgc=lambda: TGC)                 # real clock: nothing here may sleep
    c = ctx(st)
    assert q.after(c, 7, "/status")
    assert drawing.wait(5), "the drawing thread did not start"
    t0 = time.monotonic()
    got = [q.after(c, 7, "/hedges"), q.after(c, 7, "/s"), q.after(c, 7, "/status")]
    took = time.monotonic() - t0
    assert got == [True, True, False] and took < 1.0, (got, took)
    assert "chart for /status skipped: 2 pictures already waiting" in log_lines()
    release.set()
    q.q.join()
    assert len(st.tg.photos) == 3 and all(p[0] == 7 for p in st.tg.photos)
    assert sum(1 for x in log_lines() if x.startswith("SENT PHOTO for ")) == 3


def test_queue_size_is_pinphones():
    assert (Q.CHART_QUEUE, Q.CHART_MAX_BYTES, Q.PHOTO_TRIES) == (pp.CHART_QUEUE, pp.CHART_MAX_BYTES, pp.PHOTO_TRIES)


# ---- one(): the drawing thread's side -----------------------------------------------------------------------------------
def test_stale_after_120_s():
    clear_log()
    drawn = []
    st = state(chart_fn=lambda k, c: drawn.append(k) or (b"P", "c"))
    q, clock = cq(st)
    clock.t = 1000.0 + 121
    q.one(job(queued=1000.0))
    assert drawn == [] and st.tg.photos == []
    assert log_lines() == ["chart for /status dropped: its turn came 121 s after the words (limit 120 s)"]
    clock.t = 1000.0 + 120
    q.one(job(queued=1000.0))
    assert drawn == ["status"] and len(st.tg.photos) == 1, "exactly 120 s is still in time"
    st.chart_stale_s = 5
    clock.t = 1006.0
    q.one(job(queued=1000.0))
    assert drawn == ["status"], "a planted chart_stale_s wins over tgcharts.STALE_S"


def test_photo_retries_after_5_and_20_s():
    clear_log()
    for n, err, want_photos, want_slept, raises in (
            (0, None, 1, [], None),
            (1, OSError("reset"), 1, [5], None),
            (2, OSError("reset"), 1, [5, 20], None),
            (3, OSError("reset"), 0, [5, 20], OSError),
            (2, urllib.error.HTTPError("u", 503, "busy", {}, None), 1, [5, 20], None),
            (1, urllib.error.HTTPError("u", 429, "slow", {}, None), 1, [5], None),
            (1, urllib.error.HTTPError("u", 400, "bad", {}, None), 0, [], urllib.error.HTTPError),
            (1, RuntimeError("sendPhoto refused: no"), 0, [], RuntimeError)):
        st = state(chart_fn=lambda k, c: (b"PNG", "cap"), tg=FlakyTG(n, err))
        q, clock = cq(st)
        try:
            q.one(job())
            got = None
        except Exception as e:                              # noqa: BLE001
            got = type(e)
        assert (len(st.tg.photos), clock.slept, got) == (want_photos, want_slept, raises), (n, err)
    assert "chart for /status: send failed (reset) -- trying again in 5 s" in log_lines()
    assert "chart for /status: send failed (reset) -- trying again in 20 s" in log_lines()


def test_matplotlib_missing_turns_charts_off():
    clear_log()

    def no_mpl(k, c):
        raise ImportError("No module named 'matplotlib'")
    st = state(chart_fn=no_mpl)
    q, _c = cq(st)
    q.one(job())
    assert st.charts_on is False and st.tg.photos == [] and log_lines()[-1].startswith("charts OFF until restart")
    st2 = state(chart_fn=lambda k, c: (_ for _ in ()).throw(ImportError("No module named 'numpy'")))
    q2, _c = cq(st2)
    try:
        q2.one(job())
    except ImportError:
        pass
    else:
        raise AssertionError("another missing module is raised (the loop logs it)")
    assert st2.charts_on is True


def test_nothing_to_draw_and_too_big():
    clear_log()
    st = state(chart_fn=lambda k, c: None)
    q, _c = cq(st)
    q.one(job())
    assert st.tg.photos == [] and log_lines()[-1] == "chart for /status: nothing live to draw (0.0 s)"
    st = state(chart_fn=lambda k, c: (b"x" * 11, "c"))
    q, _c = cq(st, max_bytes=10)
    q.one(job())
    assert st.tg.photos == [] and log_lines()[-1] == "chart for /status not sent: 11 bytes is over 10"
    st = state()                                            # chart_fn None: tgcharts.build (here TGC.build)
    q, _c = cq(st)
    q.one(job(kind="hedges", cmd="/hedges"))
    assert st.tg.photos == [(7, b"PNG-hedges", "caption hedges")]
    assert log_lines()[-1] == "SENT PHOTO for /hedges: 0 KB, drawn in 0.0 s -- caption hedges"


def test_the_drawing_thread_survives_a_failure():
    calls = []

    def fn(k, c):
        calls.append(k)
        if len(calls) == 1:
            raise ValueError("bad data")
        return b"PNG", "ok"
    st = state(chart_fn=fn)
    q = Q.ChartQueue(st, tgc=lambda: TGC)
    c = ctx(st)
    assert q.after(c, 7, "/status")
    q.q.join()
    assert q.after(c, 7, "/hedges")
    q.q.join()
    assert calls == ["status", "hedges"] and len(st.tg.photos) == 1
    assert any("ValueError: bad data" in x for x in log_lines())


# ---- against the Phone's own methods ------------------------------------------------------------------------------------
def _phone(**kw):
    led = ledger()
    ph = pp.Phone({"chat_id": 7}, FlakyTG(), ledger=led, now_fn=lambda: T)
    ph.active = lambda: ("pin", "ladder")
    for k, v in kw.items():
        setattr(ph, k, v)
    return ph


def test_chart_ctx_and_after_vs_phone():
    """The same job and the same chart context as Phone.chart_after / _chart_ctx (the real tgcharts' kinds and LEDGER_KINDS),
    with the clock frozen for both."""
    saved = time.monotonic
    time.monotonic = lambda: 4242.0
    try:
        for text in ("/status", "/hedges", "/bars", "/today", "/funds", "/pause", "/help", "/Status@x y"):
            jobs = []
            for side in ("old", "new"):
                ph = _phone(charts_on=True, _bars_d={"bars": 1})
                ph._chart_q = queue.Queue(maxsize=2)          # (no drawing thread on either side)
                if side == "old":
                    r = ph.chart_after(7, text)
                    q = ph._chart_q
                else:
                    cq_ = Q.ChartQueue(ph)
                    cq_.q = queue.Queue(maxsize=2)
                    c = Ctx.from_phone(ph, text, chat_id=7)
                    c.active = ph.active
                    r = cq_.after(c, 7, text)
                    q = cq_.q
                j = q.get_nowait() if q.qsize() else None
                if j is not None:               # the legacy dict and the new ChartCtx, as the pictures read them
                    x = as_ctx(j["ctx"])
                    led = x.ledger
                    x = {k: getattr(x, k) for k in ("now", "bs_getter", "bs_procs", "funds_what", "active", "bars",
                                                     "first_live_day")}
                    j = dict(j, ctx=x, ledger=None if led is None else {k: getattr(led, k) for k in Q.LEDGER_LISTS})
                jobs.append((r, j))
            assert jobs[0] == jobs[1], (text, jobs)
    finally:
        time.monotonic = saved


def test_one_vs_phone():
    """Phone._chart_one and ChartQueue.one on the same jobs: the same photos, sleeps, exceptions, charts_on and log lines
    (time.monotonic / time.sleep planted for both, as the Phone reads them)."""
    saved = time.monotonic, time.sleep
    clock = Clock(10_000.0)
    time.monotonic, time.sleep = clock.monotonic, clock.sleep
    try:
        cases = [
            dict(fn=lambda k, c: (b"PNG", "cap"), tg=(0, None), queued=10_000.0),
            dict(fn=lambda k, c: (b"PNG", "cap"), tg=(2, OSError("reset")), queued=10_000.0),
            dict(fn=lambda k, c: (b"PNG", "cap"), tg=(3, OSError("reset")), queued=10_000.0),
            dict(fn=lambda k, c: (b"PNG", "cap"), tg=(1, RuntimeError("refused")), queued=10_000.0),
            dict(fn=lambda k, c: (b"PNG", "cap"), tg=(0, None), queued=10_000.0 - 500),
            dict(fn=lambda k, c: None, tg=(0, None), queued=10_000.0),
            dict(fn=lambda k, c: (b"x" * (pp.CHART_MAX_BYTES + 1), "c"), tg=(0, None), queued=10_000.0),
            dict(fn=lambda k, c: (_ for _ in ()).throw(ImportError("matplotlib missing")), tg=(0, None), queued=10_000.0),
        ]
        for i, cs in enumerate(cases):
            out = []
            for side in ("old", "new"):
                clear_log()
                clock.t, clock.slept = 10_000.0, []
                ph = _phone(charts_on=True, chart_fn=cs["fn"], chart_stale_s=120, tg=FlakyTG(*cs["tg"]))
                j = dict(job(queued=cs["queued"]))
                try:
                    (ph._chart_one if side == "old" else Q.ChartQueue(ph).one)(j)
                    err = None
                except Exception as e:                      # noqa: BLE001
                    err = (type(e).__name__, str(e))
                out.append((ph.tg.photos, list(clock.slept), err, ph.charts_on, log_lines()))
            assert out[0] == out[1], (i, out)
    finally:
        time.monotonic, time.sleep = saved


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
    print("test_chartq: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
