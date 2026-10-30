r"""phone/app.py -- the phone's RUNTIME: class Phone (the Telegram long poll, the ticks, the heartbeat, the hello) and
main(). research/pinphone.py (the launcher boot_all starts) imports this and runs main(); if that fails before the first
answered poll it runs research/pinphone_legacy.py instead (v-tg-rebuild step 11, 2026-10-30).

WHAT RUNS WHERE
  the poll thread    Phone.run -> loop_once: heartbeat, poll_once (getUpdates, 25 s long poll; each message answered by
                     phone/router.py, the reply sent, its picture queued), then the update flag (phone/commands/update.py
                     flag_tick), the alerts (phone/alerts.py tick) and the sends the connection dropped (resend_tick).
                     Every tick's failure is logged and the loop goes on.
  the charts thread  phone/chartq.py: one short queue (2) and one drawing thread. THE POLL THREAD NEVER WAITS FOR A
                     PICTURE (a full queue drops it, logged; the words already went).
  the process table  botdata/procs.py's refresher thread (every 90 s): Windows itself in milliseconds, WMI only when that
                     fails -- so neither a command nor the alerts behind it wait on a 10-35 s WMI read.
  workers            the controls (/pause /start /stop yes) and /update each run on their own daemon thread and report
                     through say().
State kept here between messages: the offset, muted, the five alert fields (last_state, last_rec, seen_losses,
last_daily, disk_level), busy / _updating / _exit_now, /bars' numbers for its picture, the resend queue. The seams the
self-test and the golden harness plant are the Phone attributes listed in __init__ (phone/context.py reads them).

THE OPERATOR'S NOTES (from pinphone.py, unchanged):
pinphone.py -- the bot in your pocket: a Telegram bot you message.

THE OPERATOR, 2026-09-17: "I want a way to access from my phone."

WHY TELEGRAM AND NOT A WEB PAGE. A web page on the laptop needs a port opened
to the internet (or a tunnel), and then anything on it -- including PAUSE and
STOP -- is reachable by whoever finds the address. A Telegram bot opens no
port: this program POLLS Telegram's servers for messages, answers only ONE
chat (yours, paired once with a secret), and works on cellular anywhere.
Nothing about the account, the key or the tape leaves the machine except the
text of the replies.

SETUP (once, two minutes, on the phone):
  1. In Telegram, message @BotFather, send /newbot, pick a name. It replies
     with a TOKEN like 123456789:AAH...  Paste it into C:\kals\telegram.json:
        {"token": "123456789:AAH...", "secret": "any words you choose"}
  2. Start this program (boot_all.ps1 starts it when the file exists).
  3. Open your new bot in Telegram and send:   /pair any words you choose
     From then on only that chat is answered. Anyone else is ignored.

COMMANDS
  /status     what the desktop banner shows, with its evidence
  /today  /yesterday  /days      money, %% return, closes, fills, hours up
  /open       open bets            /market    how active sellers are
  /losses     every bot's losses   /hedges    insurance and whether it was needed
  /stats      the whole record by window: money, win rate vs break-even, losses, timing
  /bots       every bot and its pot (subaccount): running, money by window, cash, the all-bots total
  /pin  /forecaster (/fc)  /ladder  /weather (/wx)  /fx  /jb (/jumpband)   one bot in full: running or not and why, version,
              settings, money today / yesterday / 7 days / month / all time, worst and best,
              open bets, cash, last markets, what its log did today (research/botstats.py)
  /race       the live coin race now (real money, main account; since v-race-snowball its bets grow
              with the bank), its last 10 races, and its money by window
  /racestats  the coin race record, and the paper arms on the same races
  /bars       every running test against its pre-registered bar: the numbers
              so far, days into the window, PASS / KILL / EXTEND / TOO EARLY
  /funds (/bank /accounts)   every Kalshi account's money: cash in each pool, open bets,
              total, what runs there, each bot's bet size now, its last 7 ET days of gains
              and losses from Kalshi's settlements, and the grand total
  /speed      did the move to the AWS server (10-27) win orders the laptop lost: the pin bot's
              order times and empty orders, home against server, and what speed added in $
              (an estimate); a line for the FX taker, forecaster and coin race
  /server     the server: CPU, memory, disk, uptime, a waiting Windows restart, the time to
              Kalshi, every pot's money (botstats' cache), the AWS bill (/server help: connect it)
  /pause     no new bets, wait for open ones, stop     /start    trade again
  /stop yes   stop right now (the word 'yes' is required)
  /mute  /unmute   alerts off / on          /help

ALERTS it sends by itself: every change of state (TRADING -> NOT RUNNING,
SAFETY BRAKE, PAUSED...), every LOSING close with its story, LOW DISK (once
under 8 GB free, again under 6 GB -- run_all.ps1 stops both recorders for good
at 5 GB and that tape cannot be recreated; re-armed once it climbs back over
9 GB), and one summary of yesterday at 8:00 AM ET. Routine wins are never
sent (the operator asked not to be cluttered with settlements).

The controls are the same functions the desktop app uses (research\pindesk.py):
PAUSE waits for open bets, STOP asks for 'yes', the kill checks the pid's
command line first. The stand-down flag is shared, so the phone and the
desktop always agree.

HOW A REPLY LOOKS (2026-10-18, the operator: "They're blobs of text and hard
to find my numbers"): Telegram HTML -- a headline with the number that
matters, short sections under bold headers, small aligned tables, money with
its percentage beside it, and the long sentences kept whole behind a tap (an
expandable quote). Only the layout changed: every figure is the one the plain
text carried, from the same source. See PRESENTATION below.

CHARTS (2026-10-18, the operator: "do actual x y charts and that solution should work for most
commands"): right after the words, most commands also get a real x-y chart, a PNG sent with sendPhoto
-- the running total through the day, $ and % of the bank by day, each running account's money over
time, a bot's running total and win rate, losses over time, each running test against its bar.
research/tgcharts.py draws them, from the same functions the words use, on ONE background thread
(never on the poll loop: alerts, /pause and /stop never wait for a picture). "charts": false in
telegram.json turns them off; without matplotlib the words still go, and pinphone.log says why.

    python research/pinphone.py --selftest
    python research/pinphone.py --preview        # print what each command would send (as the phone shows it)
    python research/pinphone.py                  # run (needs C:\kals\telegram.json)
"""
import json
import os
import sys
import threading
import time
import traceback

from botdata import paths as _paths
from botdata import procs as _procs
from phone import alerts as _alerts
from phone import chartq as _chartq
from phone import router as _router
from phone import shared as S
from phone.chartq import ChartQueue
from phone.commands import update as _update
from phone.context import Ctx
from phone.html import Html, esc, html_to_plain, split_html, split_text
from phone.log import cprint, log
from phone.transport import FakeTelegram, Telegram, net_error
from pindesk import Ledger, et_str
import pindesk


class Phone:
    """The phone's runtime: the Telegram poll loop and what it keeps between messages. v-tg-rebuild step 10 (2026-10-30):
    every reply comes from phone/router.py (dispatch: pairing, the paired chat, the ledger refresh, a paused bot's page,
    the command modules in research/phone/commands, the unknown-message answer); the alerts are phone/alerts.py, the
    update flag phone/commands/update.py, the pictures phone/chartq.py. What stays here is state and the loop."""

    pp = S                                  # the helpers module the commands read (Ctx.from_phone)

    def __init__(self, cfg, transport, ledger=None, health_fn=None, cfg_path=S.CONFIG, now_fn=None,
                 procs_fn=None, versions_path=None, race30_epoch=None):
        self.cfg = cfg
        self.cfg_path = cfg_path
        self.tg = transport
        self.ledger = ledger or Ledger()
        self.health_fn = health_fn or (lambda: pindesk.health(self.ledger))
        self.now = now_fn or time.time
        self.offset = None
        self.polled_ok = False                  # a getUpdates has answered (the launcher's fallback stops counting)
        self.muted = False
        # the alerts tick's memory (phone/alerts.py reads and writes these five on the runtime)
        self.last_state = None
        self.last_rec = None
        self.seen_losses = None
        self.last_daily = None
        self.disk_level = 0                     # disk_alert(): 0 armed, 8 / 6 = that line already sent
        self.bars_fn = None                     # the self-test plants /bars' text
        self.busy = False                       # a control is running (phone/commands/controls.py)
        self._updating = False                  # an /update check is running (phone/commands/update.py)
        self._exit_now = False                  # /update passed: the poll loop confirms the offset, then exits
        self.update_start = None                # the update flag's /update (None = update.start_update; tests plant)
        # /stats, /race, /racestats read the process table, VERSIONS.md and
        # the v-race30 clock; the self-test plants all three.
        self.procs_fn = procs_fn or S.python_procs
        self.versions_path = versions_path or S.VERSIONS_MD
        self.race30_epoch = race30_epoch or S.RACE30_EPOCH
        # /bots /pin /forecaster /ladder and /race's money windows read Kalshi
        # through botstats. None = botstats' own: kauth.get (GET only, 60 s
        # cache) and its own process-table read (about 1.5 s natively). The self-test plants
        # a fake Kalshi and a process table here.
        self.bs_getter = None
        self.bs_procs = None
        # /funds reads Kalshi through this getter; None = botstats.default_getter() (kauth.get, GET only).
        # The self-test plants a fake Kalshi here.
        self.funds_getter = None
        # CHARTS (2026-10-18): a picture after the words, drawn on one background thread (phone/chartq.py).
        # Off unless main() turns them on, so every self-test Phone sends words only unless it asks.
        self.charts_on = False
        self.chart_fn = None                    # None = tgcharts.build; the self-test plants its own
        self.chart_stale_s = None               # None = tgcharts.STALE_S
        self.charts = ChartQueue(self, kind_of=_router.kind_of)
        self._bars_d = None                     # /bars' gathered numbers, for its picture
        self._resend = []                       # sends the connection dropped (say -> resend_tick)
        self._resend_lock = threading.Lock()
        # /server's readings (2026-10-27); None = the real ones: machine_read, kalshi_ping, botstats.cached_pots, and
        # _aws_http for the metadata service and AWS. The self-test plants all four.
        self.machine_fn = None
        self.ping_fn = None
        self.pots_fn = None
        self.aws_http = None

    # ---- helpers ----
    @property
    def chat_id(self):
        return self.cfg.get("chat_id")

    def ctx(self, text="", chat_id=None):
        """The Ctx a command, an alert or a picture reads (phone/context.py): this runtime's seams, now."""
        return Ctx.from_phone(self, text, chat_id=chat_id)

    def active(self):
        """The bots shown now (v-tg-active, 2026-10-30): botstats.active_bots -- a live copy running and no stop file; the
        pin bot always. Fail-safe: any error shows every bot (a command never dies on it)."""
        return self.ctx().active()

    def say(self, text, chat_id=None):
        """Send, and LOG WHAT WAS SENT. 2026-09-23: the operator got a
        RECORDER SILENT alert and the log held no trace of it -- only
        failures were logged -- so there was no way to audit whether an
        alert had fired, which is the whole point of having alerts.
        2026-10-23: a send the CONNECTION dropped is kept and tried again
        (resend_tick) -- that night the 'DOWN -> TRADING' alert was lost
        and the operator believed the bots were still down."""
        cid = chat_id or self.chat_id
        flat = " | ".join((html_to_plain(text) if getattr(text, "is_html", False) else str(text)).splitlines())
        if cid is None:
            log("NOT SENT (no paired chat): %s" % flat[:200])
            return
        try:
            self.tg.send(cid, text)
            log("SENT: %s" % flat[:300])
        except Exception as e:                            # noqa: BLE001
            again = net_error(e)
            log("send failed: %s -- %stext was: %s" % (e, "will try again; " if again else "", flat[:200]))
            if again:
                with self._resend_lock:
                    self._resend.append({"chat": cid, "text": text, "t": self.now(),
                                         "next": time.monotonic() + S.RESEND_GAP_S, "flat": flat})
                    del self._resend[:-S.RESEND_KEEP]

    def resend_tick(self):
        """Try the sends the connection dropped again, oldest first, each RESEND_GAP_S apart, for RESEND_FOR_S.
        A late one says so first ('sent late, from 9:53 PM ET'), since its numbers are from then. Never raises."""
        now_m = time.monotonic()
        with self._resend_lock:
            due = [x for x in self._resend if x["next"] <= now_m]
        for x in due:
            if self.now() - x["t"] > S.RESEND_FOR_S:
                with self._resend_lock:
                    if x in self._resend:
                        self._resend.remove(x)
                log("gave up resending (over %d min old): %s" % (S.RESEND_FOR_S // 60, x["flat"][:150]))
                continue
            late = "⏱ Sent late -- from %s ET; the connection dropped it then." % et_str(x["t"])
            t = x["text"]
            body = Html("<i>%s</i>\n%s" % (esc(late), t)) if getattr(t, "is_html", False) else "%s\n%s" % (late, t)
            try:
                self.tg.send(x["chat"], body)
                log("SENT (late, from %s): %s" % (et_str(x["t"]), x["flat"][:250]))
                with self._resend_lock:
                    if x in self._resend:
                        self._resend.remove(x)
            except Exception as e:                        # noqa: BLE001
                x["next"] = time.monotonic() + S.RESEND_GAP_S
                if not net_error(e):
                    with self._resend_lock:
                        if x in self._resend:
                            self._resend.remove(x)
                log("resend failed: %s" % e)
                break                                     # the connection is still down: the rest wait too

    # ---- dispatch: phone/router.py ----
    def handle(self, chat_id, text):
        """Reply text for one incoming message, or None to ignore it (router.dispatch)."""
        return _router.dispatch(self, chat_id, text)

    # ---- the ticks ----
    def update_flag_tick(self):
        """results/pinphone.update: its presence runs /update exactly as the command does (update.flag_tick). The reply
        said, or None when there is no flag."""
        return _update.flag_tick(self.ctx(), start=self.update_start)

    def alerts_tick(self):
        """Called every poll cycle. Sends only on CHANGE (phone/alerts.py: tick)."""
        return _alerts.tick(self.ctx())

    def daily_alert(self, d, now):
        """The 8 AM summary of day `d` (phone/alerts.py: daily_alert)."""
        return _alerts.daily_alert(self.ctx(), d, now)

    # ---- charts (2026-10-18): phone/chartq.py ----
    def chart_after(self, chat_id, text):
        """Queue the picture for a command whose words were just sent. NEVER RAISES AND NEVER WAITS (ChartQueue.after).
        Returns True when queued."""
        try:
            return self.charts.after(self.ctx(text, chat_id=chat_id), chat_id, text)
        except Exception:                                       # noqa: BLE001
            log(traceback.format_exc())
            return False

    def _chart_ctx(self, kind, tgc):
        """What the picture reads, fixed right after the words were built (chartq.chart_ctx: a ChartCtx)."""
        return _chartq.chart_ctx(self.ctx(), kind, tgc)

    @property
    def _chart_q(self):
        return self.charts.q

    # ---- main loop ----
    def poll_once(self, timeout=25):
        if getattr(self, "_exit_now", False):           # /update passed: confirm what was handled, then leave
            try:
                self.tg.get_updates(self.offset, timeout=0)
            except Exception:                           # noqa: BLE001
                pass
            log("/update: exiting so boot_all starts the new code")
            os._exit(0)
        try:
            updates = self.tg.get_updates(self.offset, timeout=timeout)
        except Exception as e:                            # noqa: BLE001
            log("getUpdates failed: %s" % e)
            time.sleep(10)
            return
        self.polled_ok = True
        for u in updates:
            self.offset = max(self.offset or 0, int(u.get("update_id", 0)) + 1)
            m = u.get("message") or {}
            chat = (m.get("chat") or {}).get("id")
            handled = True
            try:
                reply = self.handle(chat, m.get("text"))
            except Exception as e:                        # noqa: BLE001
                reply = "error: %s" % e
                handled = False
                log(traceback.format_exc())
            if reply:
                self.say(reply, chat_id=chat)
                if handled:
                    self.chart_after(chat, m.get("text"))     # queued, never drawn here (see chart_after)

    def heartbeat(self):
        """results/pinphone.heartbeat: the time now (boot_all and the operator read it)."""
        try:
            _paths.check_write(S.HEARTBEAT)        # v-tg-rebuild step 2: never the live heartbeat under KALS_TESTING=1
            with open(S.HEARTBEAT, "w", encoding="utf-8") as fh:
                fh.write(time.strftime("%Y-%m-%dT%H:%M:%S"))
        except OSError:
            pass

    def start(self):
        """Everything before the loop: the command modules, the process-table refresher, the hello."""
        log("pinphone starting; paired chat: %s; charts %s" % (self.chat_id, "on" if self.charts_on else "off"))
        failed = _router.discover()
        if failed:
            log("command modules that did not load (their commands say so): %s" % ", ".join(sorted(failed)))
        # the process table for /stats and /race, read off the poll thread (botdata.procs)
        _procs.start_refresher()
        if self.chat_id:
            self.say(S.UP_TEXT)

    def loop_once(self):
        """One pass: the heartbeat, one long poll (every message answered), then the update flag, the alerts and the
        sends the connection dropped. Each tick's failure is logged and the loop goes on."""
        self.heartbeat()
        self.poll_once()
        for tick in (self.update_flag_tick, self.alerts_tick, self.resend_tick):
            try:
                tick()
            except Exception:                            # noqa: BLE001
                log(traceback.format_exc())

    def run(self):
        self.start()
        while True:
            self.loop_once()


# Every command module, imported now, each inside its own try (router.discover: a broken one costs only its commands, and
# its names answer 'this command failed to load'); /help is rebuilt from the declarations.
_router.discover()


def preview(argv=()):
    """--preview: what each command would send, AS THE PHONE SHOWS IT (tags dropped); --html prints the markup instead.
    Every declared command through the router, except the ones that change something (the controls and /update start
    workers; /pair and /mute write state). NOTE: /bots /pin /race /funds read Kalshi (GET only, botstats' getter) and
    the process table."""
    raw = "--html" in argv

    def show(x):
        return str(x) if raw or not getattr(x, "is_html", False) else html_to_plain(x)
    ph = Phone({"chat_id": 0}, FakeTelegram())
    ph.ledger.refresh()
    t0 = time.time()
    n = S.python_procs()
    cprint("(process table: %s in %.1f s -- the daemon reads it on a background thread)"
           % ("%d python processes" % len(n) if n is not None else "COULD NOT BE READ", time.time() - t0))
    for c in _router.commands():
        if c.runs_in_worker or c.name in ("/pair", "/mute"):
            continue
        t0 = time.time()
        out = ph.handle(0, c.name)
        if out is None:
            continue
        parts = split_html(out) if getattr(out, "is_html", False) else split_text(out)
        cprint("\n--- %s (%d chars, %d message(s), %.1f s) ---\n%s" % (
            c.name, len(out), len(parts), time.time() - t0, show(out)))
    return 0


def main(argv=None, state=None):
    """Run the phone: C:\\kals\\telegram.json's token and paired chat, charts on unless "charts": false. `state` (a dict,
    the launcher's) gets the Phone as state["phone"] before the loop starts, so a failure can be told apart: before the
    first answered poll (Phone.polled_ok False) the launcher runs the legacy phone instead."""
    argv = sys.argv[1:] if argv is None else list(argv)
    if "--preview" in argv:
        return preview(argv)
    try:
        with open(S.CONFIG, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as e:
        print("no usable %s (%s). See the docstring for setup." % (S.CONFIG, e))
        return 2
    if not cfg.get("token"):
        print("%s has no token" % S.CONFIG)
        return 2
    ph = Phone(cfg, Telegram(cfg["token"]))
    ph.charts_on = cfg.get("charts", True) is not False         # "charts": false in telegram.json = words only
    if state is not None:
        state["phone"] = ph
    ph.run()
    return 0
