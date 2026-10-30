"""phone/chartq.py -- the picture after the words: one short queue and one background thread that draws and sends it.

v-tg-rebuild step 9 (2026-10-30, lane F): Phone.chart_after, _chart_ctx, _ledger_snapshot, _chart_queue, _chart_loop and
_chart_one moved here VERBATIM (tests: research/phone/tests/test_chartq.py on FakeTelegram and a fake clock;
research/golden/shadow_more.py draws every golden chart kind from chart_ctx() and wants Phone._chart_ctx's PNG and
caption). Nothing is switched over yet: Phone keeps its own methods until steps 10-11.

THE RULE (DESIGN risk 9): THE POLL THREAD NEVER WAITS FOR A PICTURE. after() puts one job on a queue of CHART_QUEUE (2)
with put_nowait and returns; a full queue drops the picture (logged) -- the words already went. One daemon thread draws
the jobs in turn; a job whose turn comes more than chart_stale_s (default tgcharts.STALE_S, 120 s) after its words is
dropped; a photo the CONNECTION dropped is sent again after 5 s and 20 s (PHOTO_TRIES); a refused one is not.

STATE. ChartQueue(state): `state` is the runtime the old methods read on `self` (the Phone until step 11): charts_on
(after() checks it; a missing matplotlib turns it off), chart_fn (None = tgcharts.build), chart_stale_s, tg (send_photo),
and -- through the Ctx given to after() -- the clock, the ledger, active(), botstats' getter / process table, /bars'
numbers (ctx.state._bars_d) and the helpers module (ctx.pp: funds_what, FUNDS_WHAT, chart_markets, window_stats,
FIRST_LIVE_DAY, main_words, _bs -- the named parts of the explicit ChartCtx since step 10). monotonic / sleep are
injectable (tests); None = time.monotonic / time.sleep, looked up at each call exactly as the old code did. kind_of: the
picture kind of a command (the runtime passes the router's: the declaring Command's chart).
"""
import copy
import queue
import threading
import time
import traceback

from phone.log import log
from phone.transport import net_error

CHART_QUEUE = 2                 # from pinphone: pictures waiting to be drawn; one more is dropped (logged), never waited for
CHART_MAX_BYTES = 9_500_000     # from pinphone: Telegram takes photos up to 10 MB
PHOTO_TRIES = (5, 20)           # from pinphone: a chart the connection dropped: sent again after these many seconds
LEDGER_LISTS = ("settled", "orders", "hedges", "autosize", "external", "halts", "starts", "closes")


def _tgc():
    """research/tgcharts.py, imported on first use (it imports matplotlib only when it draws). (pinphone._tgc)"""
    import tgcharts
    return tgcharts


def command_of(text):
    """'/Status@kalsbot x' -> '/status' (chart_after's split, the same as Phone.handle's)."""
    return (text or "").strip().partition(" ")[0].lower().split("@")[0]


def ledger_snapshot(ledger):
    """A private copy of the ledger's lists (the poll thread keeps appending to the live ones). (Phone._ledger_snapshot)"""
    s = copy.copy(ledger)
    for k in LEDGER_LISTS:
        v = getattr(ledger, k, None)
        if isinstance(v, list):
            setattr(s, k, list(v))
    return s


def chart_ctx(ctx, kind, tgc):
    """What the picture reads, fixed right after the words were built: the clock, a private copy of the
    ledger's lists (this thread keeps appending to the live ones), botstats' getter and process table as
    the words use them, and /bars' gathered numbers. (Phone._chart_ctx)

    v-tg-rebuild step 10 (2026-10-30): an explicit phone.charts.ChartCtx (lane B's follow-up 1), no more the dict with
    the pinphone module as "pp": the pictures get the main account's markets, window_stats, FIRST_LIVE_DAY and
    main_words as the named functions of ctx.pp (the helpers module), botstats through ctx.pp._bs."""
    from phone.charts.ctx import ChartCtx
    act = ctx.active()
    pp = ctx.pp
    return ChartCtx(now=ctx.now(), bs_getter=ctx.bs_getter, bs_procs=ctx.bs_procs,
                    funds_what={n: pp.funds_what(n, act) for n in pp.FUNDS_WHAT}, active=act,
                    ledger=ledger_snapshot(ctx.ledger) if kind in tgc.LEDGER_KINDS else None,
                    bars=ctx.state._bars_d if kind == "bars" else None,
                    botstats=pp._bs, markets=pp.chart_markets, window_stats=pp.window_stats,
                    first_live_day=pp.FIRST_LIVE_DAY, main_words=pp.main_words)


class ChartQueue:
    """The chart queue and its drawing thread (the thread starts with the first job)."""

    def __init__(self, state, maxsize=CHART_QUEUE, tries=PHOTO_TRIES, max_bytes=CHART_MAX_BYTES, monotonic=None,
                 sleep=None, tgc=None, kind_of=None):
        self.state = state
        self._kind_of = kind_of             # (cmd) -> picture kind; None = tgcharts.kind_of (the router passes its own)
        self.maxsize = maxsize
        self.tries = tuple(tries)
        self.max_bytes = max_bytes
        self._monotonic = monotonic
        self._sleep = sleep
        self._tgc = tgc or _tgc
        self.q = None
        self._lock = threading.Lock()

    def monotonic(self):
        return (self._monotonic or time.monotonic)()

    def sleep(self, s):
        return (self._sleep or time.sleep)(s)

    # ---- the poll thread's side: NEVER RAISES AND NEVER WAITS ----
    def after(self, ctx, chat_id, text):
        """Queue the picture for a command whose words were just sent (Phone.chart_after). Only the paired chat
        (ctx.cfg's chat_id), only a command tgcharts draws (never /pause /start /stop), nothing while charts are off.
        A full queue drops the picture (logged); the words already went. True when queued."""
        try:
            if not self.state.charts_on or chat_id is None or chat_id != ctx.cfg.get("chat_id"):
                return False
            cmd = command_of(text)
            tgc = self._tgc()
            kind = (self._kind_of or tgc.kind_of)(cmd)
            if kind is None:
                return False
            job = {"kind": kind, "cmd": cmd, "chat": chat_id, "queued": self.monotonic(),
                   "ctx": chart_ctx(ctx, kind, tgc)}
            try:
                self.queue().put_nowait(job)
            except queue.Full:
                log("chart for %s skipped: %d pictures already waiting" % (cmd, self.maxsize))
                return False
            return True
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
            return False

    def queue(self):
        """The queue, made (and its thread started) on first use. (Phone._chart_queue)"""
        with self._lock:
            if self.q is None:
                self.q = queue.Queue(maxsize=self.maxsize)
                threading.Thread(target=self.loop, name="charts", daemon=True).start()
        return self.q

    # ---- the drawing thread ----
    def loop(self):
        """(Phone._chart_loop) one job at a time, for ever; a failure is logged and the next job comes."""
        while True:
            job = self.q.get()
            try:
                self.one(job)
            except Exception:                                   # noqa: BLE001
                log(traceback.format_exc())
            finally:
                self.q.task_done()

    def one(self, job):
        """Draw one job and send it (Phone._chart_one): dropped when stale; charts off for good when matplotlib is
        missing; nothing when there is nothing to draw or it is too big; a dropped connection retried per `tries`."""
        st = self.state
        stale = st.chart_stale_s if st.chart_stale_s is not None else self._tgc().STALE_S
        waited = self.monotonic() - job["queued"]
        if waited > stale:
            log("chart for %s dropped: its turn came %.0f s after the words (limit %d s)" % (job["cmd"], waited, stale))
            return
        t0 = self.monotonic()
        try:
            got = (st.chart_fn or self._tgc().build)(job["kind"], job["ctx"])
        except ImportError as e:
            if "matplotlib" in str(e):
                st.charts_on = False
                log("charts OFF until restart: %s -- the words still go. Fix: C:\\Python314\\python.exe -m pip "
                    "install matplotlib, then restart pinphone." % e)
                return
            raise
        if not got:
            log("chart for %s: nothing live to draw (%.1f s)" % (job["cmd"], self.monotonic() - t0))
            return
        data, caption = got
        if len(data) > self.max_bytes:
            log("chart for %s not sent: %d bytes is over %d" % (job["cmd"], len(data), self.max_bytes))
            return
        for k, wait in enumerate((0,) + self.tries):        # 2026-10-23: the connection dropped charts that night
            if wait:
                self.sleep(wait)
            try:
                st.tg.send_photo(job["chat"], data, caption)
                break
            except Exception as e:                          # noqa: BLE001
                if k == len(self.tries) or not net_error(e):
                    raise
                log("chart for %s: send failed (%s) -- trying again in %d s" % (job["cmd"], e, self.tries[k]))
        log("SENT PHOTO for %s: %d KB, drawn in %.1f s -- %s" % (job["cmd"], len(data) // 1024,
                                                                 self.monotonic() - t0, (caption or "")[:120]))
