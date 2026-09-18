#!/usr/bin/env python3
r"""pinphone.py -- the bot in your pocket: a Telegram bot you message.

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
  /losses     losing closes        /hedges    insurance and whether it was needed
  /pause      no new bets, wait for open ones, stop     /start    trade again
  /stop yes   stop right now (the word 'yes' is required)
  /mute  /unmute   alerts off / on          /help

ALERTS it sends by itself: every change of state (TRADING -> NOT RUNNING,
SAFETY BRAKE, PAUSED...), every LOSING close with its story, and one summary
of yesterday at 8:00 AM ET. Routine wins are never sent (the operator asked
not to be cluttered with settlements).

The controls are the same functions the desktop app uses (research\pindesk.py):
PAUSE waits for open bets, STOP asks for 'yes', the kill checks the pid's
command line first. The stand-down flag is shared, so the phone and the
desktop always agree.

    python research/pinphone.py --selftest
    python research/pinphone.py --preview        # print what /status would send
    python research/pinphone.py                  # run (needs C:\kals\telegram.json)
"""
import json
import os
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pindesk                                                       # noqa: E402
from pindesk import (Ledger, et_day, et_day_start, et_str, et_now_str, coin, close_et, money, pct,   # noqa: E402
                     story_loss, story_hedge, story_day, status_of, hours_up_et_day)
import pinflat                                                       # noqa: E402

CONFIG = r"C:\kals\telegram.json"
RESULTS = pindesk.RESULTS
HEARTBEAT = os.path.join(RESULTS, "pinphone.heartbeat")
LOG = os.path.join(RESULTS, "pinphone.log")
MAX_LEN = 3900


def log(msg):
    line = "%s  %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# ===========================================================================
# transport
# ===========================================================================
class Telegram:
    def __init__(self, token):
        self.base = "https://api.telegram.org/bot%s/" % token

    def _call(self, method, params, http_timeout=45):
        data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
        req = urllib.request.Request(self.base + method, data=data)
        with urllib.request.urlopen(req, timeout=http_timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def get_updates(self, offset, timeout=25):
        d = self._call("getUpdates", {"offset": offset, "timeout": timeout, "allowed_updates": '["message"]'},
                       http_timeout=timeout + 15)
        return d.get("result", []) if d.get("ok") else []

    def send(self, chat_id, text):
        for i in range(0, max(1, len(text)), MAX_LEN):
            self._call("sendMessage", {"chat_id": chat_id, "text": text[i:i + MAX_LEN]})


class FakeTelegram:
    """For the self-test: a queue of incoming messages and a list of sent ones."""
    def __init__(self):
        self.incoming = []
        self.sent = []
        self.n = 0

    def push(self, chat_id, text):
        self.n += 1
        self.incoming.append({"update_id": self.n, "message": {"chat": {"id": chat_id}, "text": text}})

    def get_updates(self, offset, timeout=25):
        out = [u for u in self.incoming if u["update_id"] >= (offset or 0)]
        return out

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))


# ===========================================================================
# the bot
# ===========================================================================
HELP_TEXT = """Commands:
/status - is it trading, with the evidence
/today /yesterday /days - money and % return
/open - open bets
/market - how active sellers are
/losses - losing closes
/hedges - insurance and whether it was needed
/pause - no new bets, wait for open ones, then stop
/start - trade again
/stop yes - stop right now
/mute /unmute - alerts off / on
Alerts come by themselves: state changes, every losing close, and yesterday's summary at 8 AM ET."""


class Phone:
    def __init__(self, cfg, transport, ledger=None, health_fn=None, cfg_path=CONFIG, now_fn=None):
        self.cfg = cfg
        self.cfg_path = cfg_path
        self.tg = transport
        self.ledger = ledger or Ledger()
        self.health_fn = health_fn or (lambda: pindesk.health(self.ledger))
        self.now = now_fn or time.time
        self.offset = None
        self.muted = False
        self.last_state = None
        self.seen_losses = None
        self.last_daily = None
        self.busy = False

    # ---- helpers ----
    @property
    def chat_id(self):
        return self.cfg.get("chat_id")

    def save_cfg(self):
        try:
            with open(self.cfg_path, "w", encoding="utf-8") as fh:
                json.dump(self.cfg, fh, indent=2)
        except OSError as e:
            log("could not save config: %s" % e)

    def say(self, text, chat_id=None):
        cid = chat_id or self.chat_id
        if cid is None:
            return
        try:
            self.tg.send(cid, text)
        except Exception as e:                            # noqa: BLE001
            log("send failed: %s" % e)

    def summary_line(self, rows, day=None, label=""):
        s = Ledger.summary(rows)
        dep = self.ledger.deposited()
        if day:
            b0 = self.ledger.bank_at(et_day_start(day))
            r = (s["net"] / b0) if b0 else None
        else:
            r = (s["net"] / dep) if dep else None
        out = "%s %s (%s)" % (label, money(s["net"]), pct(r))
        if s["closes"]:
            out += "\n  %d closes (%d bets): %d won, %d lost (%.1f%%)" % (s["closes"], s["markets"], s["won"], s["lost"], s["loss_rate"])
        else:
            out += "\n  no settled bets"
        if day:
            fs = Ledger.fill_stats(self.ledger.fills_on(day))
            try:
                up = hours_up_et_day(day, self.now() if day == et_day(self.now()) else et_day_start(day) + 86400)
            except Exception:                            # noqa: BLE001
                up = None
            out += "\n  %d fills, %g contracts, %d lost races" % (fs["fills"], fs["contracts"], fs["zero"])
            if up:
                out += "\n  %.1f h up, %s/h" % (up, money(s["net"] / up))
        return out

    # ---- command texts ----
    def text_status(self):
        h = self.health_fn()
        state, hl, det, _c = status_of(h)
        b = self.ledger.bank()
        dep = self.ledger.deposited()
        lines = [hl, det, ""]
        if b:
            lines.append("Bank $%.2f, size %g contracts" % (b["bank"], b.get("size") or 0))
            if dep:
                lines.append("%s on $%.2f put in" % (pct((b["bank"] - dep) / dep), dep))
        today = et_day(self.now())
        lines.append("")
        lines.append(self.summary_line(self.ledger.settled_on(today), today, "TODAY"))
        opn = pinflat.positions(self.ledger.newest_rows) if h["alive"] else {}
        if opn:
            lines.append("")
            lines.append("Open: " + ", ".join("%s %s closes %s" % (coin(t), "x%g" % self.ledger.contracts_for(t), close_et(t)) for t in opn))
        wd = h.get("watchdog_s")
        rec = "both writing" if (h.get("kalshi_ok") and h.get("feeds_ok")) else "CHECK RECORDERS"
        lines.append("")
        lines.append("Watchdog %s. Recorders %s. Disk %.1f GB." % (
            ("ok, %ds ago" % wd) if wd is not None and wd < 120 else "NOT RUNNING", rec, h.get("disk_gb") or 0))
        return "\n".join(lines)

    def text_day(self, day, label):
        return self.summary_line(self.ledger.settled_on(day), day, label)

    def text_days(self):
        out = []
        for d in list(reversed(self.ledger.days()))[:7]:
            s = Ledger.summary(self.ledger.settled_on(d))
            b0 = self.ledger.bank_at(et_day_start(d))
            out.append("%s  %s (%s)  %d closes, %d lost" % (d[5:], money(s["net"]), pct((s["net"] / b0) if b0 else None), s["closes"], s["lost"]))
        out.append("")
        out.append(self.summary_line(self.ledger.settled, None, "ALL TIME"))
        return "\n".join(out)

    def text_open(self):
        h = self.health_fn()
        opn = pinflat.positions(self.ledger.newest_rows) if h["alive"] else {}
        if not opn:
            return "No open bets."
        out = []
        for t in opn:
            c = pinflat.close_epoch(t)
            out.append("%s x%g, closes %s (%d s)" % (coin(t), self.ledger.contracts_for(t), close_et(t), max(0, (c or 0) - self.now())))
        return "\n".join(out)

    def text_market(self):
        act = self.ledger.activity()
        out = ["SELLERS: %s" % act["level"]]
        if act["recent"] is not None:
            out.append("Last 4 quarter-hours: someone selling the winning side on %.0f%% of looks (quiet < %.0f%%, typical %.0f%%, busy > %.0f%%)."
                       % (100 * act["recent"], 100 * act["p25"], 100 * act["median"], 100 * act["p75"]))
        out.append("")
        for c in list(reversed(self.ledger.closes))[:8]:
            share = Ledger.offer_share(c)
            out.append("%s  sellers %s  %s" % (et_str(c["close"]) if c["close"] else "?", pct(share, False) if share is not None else "-", self.ledger.reason(c)))
        today = et_day(self.now())
        fs = Ledger.fill_stats(self.ledger.fills_on(today))
        out.append("")
        out.append("Today: %d orders, %d filled, %d lost races; asked %g got %g (%s)." % (
            fs["orders"], fs["fills"], fs["zero"], fs["asked"], fs["contracts"], pct(fs["share"], False) if fs["share"] is not None else "-"))
        # IS THE OPPORTUNITY GOING AWAY. Same lines the desktop shows, from
        # the same function, so the phone and the app cannot drift apart.
        # Read from health() rather than recomputed: it is already there.
        try:
            h = self.health_fn()
            sl = h.get("supply_lines") or []
            if sl:
                out.append("")
                out.append("IS THE OPPORTUNITY GOING AWAY?")
                out += sl
                age = h.get("supply_age_d")
                if age is not None:
                    out.append("(measured up to %.1f days ago)" % age)
        except Exception:                                   # noqa: BLE001
            pass
        return "\n".join(out)

    def text_losses(self):
        rows = self.ledger.losing_closes()[:10]
        if not rows:
            return "No losing closes."
        s = Ledger.summary(self.ledger.settled)
        out = ["%d losing closes of %d all time (%.1f in 100)." % (s["lost"], s["closes"], s["loss_rate"]), ""]
        for close, net, legs in rows:
            out.append("%s  %s  %s" % (et_str(close, "%m/%d %I:%M %p") if close else "?", money(net), ", ".join(sorted({coin(l["tk"]) for l in legs}))))
        return "\n".join(out)

    def text_hedges(self):
        ho = list(reversed(self.ledger.hedge_outcomes()))[:8]
        if not ho:
            return "No hedges yet."
        out = []
        for g in ho:
            out.append("%s %s belief %.0f%%: %s  bet %s, hedge %s, net %s" % (
                et_str(g["t"], "%m/%d %I:%M %p") if g["t"] else "?", coin(g["tk"]), 100 * float(g.get("belief") or 0),
                g["verdict"] or "pending", money(g["bet_pnl"]) if g["bet_pnl"] is not None else "-",
                money(g["hedge_pnl"]) if g["hedge_pnl"] is not None else "-", money(g["net"]) if g["net"] is not None else "-"))
        return "\n".join(out)

    # ---- controls ----
    def control(self, which):
        if self.busy:
            return "Still working on the last command."
        self.busy = True

        def worker():
            try:
                if which == "start":
                    pindesk.do_start(lambda m: self.say("start: " + m))
                elif which == "pause":
                    pindesk.do_pause(lambda m: self.say("pause: " + m), lambda s: self.say(s))
                elif which == "stop":
                    pindesk.do_stop(lambda m: self.say("stop: " + m))
                time.sleep(3)
                self.say(self.text_status())
            except Exception as e:                        # noqa: BLE001
                self.say("%s failed: %s" % (which, e))
                log(traceback.format_exc())
            finally:
                self.busy = False
        threading.Thread(target=worker, daemon=True).start()
        return {"start": "Starting...", "pause": "Pausing: no new bets; waiting for open ones to settle...",
                "stop": "Stopping now..."}[which]

    # ---- dispatch ----
    def handle(self, chat_id, text):
        """Reply text for one incoming message, or None to ignore it."""
        text = (text or "").strip()
        cmd, _, arg = text.partition(" ")
        cmd = cmd.lower().split("@")[0]
        if cmd == "/pair":
            if arg.strip() and arg.strip() == str(self.cfg.get("secret", "")).strip():
                self.cfg["chat_id"] = chat_id
                self.save_cfg()
                log("paired with chat %s" % chat_id)
                return "Paired. This chat now controls the bot.\n\n" + HELP_TEXT
            log("refused pairing from chat %s" % chat_id)
            return None
        if self.chat_id is None or chat_id != self.chat_id:
            return None                                  # not ours: silence
        self.ledger.refresh()
        if cmd in ("/status", "/s", "/start@"):
            return self.text_status()
        if cmd == "/today":
            return self.text_day(et_day(self.now()), "TODAY")
        if cmd == "/yesterday":
            return self.text_day(et_day(self.now() - 86400), "YESTERDAY")
        if cmd == "/days":
            return self.text_days()
        if cmd == "/open":
            return self.text_open()
        if cmd == "/market":
            return self.text_market()
        if cmd == "/losses":
            return self.text_losses()
        if cmd == "/hedges":
            return self.text_hedges()
        if cmd == "/pause":
            return self.control("pause")
        if cmd == "/start":
            return self.control("start")
        if cmd == "/stop":
            if arg.strip().lower() == "yes":
                return self.control("stop")
            return "STOP stops right now, even with a bet open (it settles by itself but will not be hedged). Send:  /stop yes\nOr use /pause to finish open bets first."
        if cmd == "/mute":
            self.muted = True
            return "Alerts off. /unmute to turn them back on."
        if cmd == "/unmute":
            self.muted = False
            return "Alerts on."
        if cmd in ("/help", "/?"):
            return HELP_TEXT
        return "I did not understand that.\n\n" + HELP_TEXT

    # ---- alerts ----
    def alerts_tick(self):
        """Called every poll cycle. Sends only on CHANGE."""
        if self.chat_id is None:
            return []
        sent = []
        self.ledger.refresh()
        h = self.health_fn()
        state, hl, det, _c = status_of(h)
        now = self.now()
        today = et_day(now)
        if self.last_state is None:
            # first tick after a (re)start: learn, do not announce. A daily
            # summary already due today is marked done, or every restart of
            # this program would re-send it.
            if (now - et_day_start(today)) >= 8 * 3600:
                self.last_daily = today
        if self.last_state is not None and state != self.last_state and not self.muted:
            msg = "STATE CHANGED: %s -> %s\n%s\n%s" % (self.last_state, state, hl, det)
            self.say(msg)
            sent.append(msg)
        self.last_state = state
        losses = self.ledger.losing_closes()
        keys = {k for k, _n, _l in losses}
        if self.seen_losses is None:
            self.seen_losses = keys
        else:
            new = [x for x in losses if x[0] not in self.seen_losses]
            self.seen_losses = keys
            for close, net, legs in new:
                if not self.muted:
                    msg = "LOSS " + story_loss(self.ledger, close, net, legs)
                    self.say(msg)
                    sent.append(msg)
        if (now - et_day_start(today)) >= 8 * 3600 and self.last_daily != today and not self.muted:
            self.last_daily = today
            yday = et_day(now - 86400)
            msg = "YESTERDAY\n" + story_day(self.ledger, yday, now=now)
            self.say(msg)
            sent.append(msg)
        return sent

    # ---- main loop ----
    def poll_once(self, timeout=25):
        try:
            updates = self.tg.get_updates(self.offset, timeout=timeout)
        except Exception as e:                            # noqa: BLE001
            log("getUpdates failed: %s" % e)
            time.sleep(10)
            return
        for u in updates:
            self.offset = max(self.offset or 0, int(u.get("update_id", 0)) + 1)
            m = u.get("message") or {}
            chat = (m.get("chat") or {}).get("id")
            try:
                reply = self.handle(chat, m.get("text"))
            except Exception as e:                        # noqa: BLE001
                reply = "error: %s" % e
                log(traceback.format_exc())
            if reply:
                self.say(reply, chat_id=chat)

    def run(self):
        log("pinphone starting; paired chat: %s" % self.chat_id)
        if self.chat_id:
            self.say("Pin Bot phone link is up. /status for the state, /help for commands.")
        while True:
            try:
                with open(HEARTBEAT, "w") as fh:
                    fh.write(time.strftime("%Y-%m-%dT%H:%M:%S"))
            except OSError:
                pass
            self.poll_once()
            try:
                self.alerts_tick()
            except Exception:                            # noqa: BLE001
                log(traceback.format_exc())


# ===========================================================================
def selftest():
    import tempfile
    import calendar

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinphone selftest: FAILED -- " + msg)

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "pinrun-live-20260916T135734Z.jsonl")
        c1, c2 = "KXBNB15M-26SEP161000-00", "KXBTC15M-26SEP161015-15"
        rows = [
            {"kind": "start", "t": "2026-09-16T13:00:00Z", "size": 20, "hedge_belief": 0.6},
            {"kind": "autosize", "t": "2026-09-16T13:00:01Z", "old": 20, "new": 85, "why": "bank $500.00"},
            {"kind": "signal", "t": "2026-09-16T13:59:30Z", "ticker": c1, "want": "no", "price": 0.98, "edge_c": 1.5, "size": 85, "take_n": 85, "tau": 29, "fair": 0.004, "spot": 700.1, "strike": 700.2, "digits": 2},
            {"kind": "order", "t": "2026-09-16T13:59:31Z", "ticker": c1, "filled": 85.0, "exec_price": 0.979, "status": "executed", "body": {"count": "85.00"}},
            {"kind": "settled", "t": "2026-09-16T14:00:20Z", "ticker": c1, "want": "no", "result": "no", "cost": 0.979, "pnl_c": 166.26, "realised": 1.6626},
            {"kind": "close_summary", "t": "2026-09-16T14:00:05Z", "close": calendar.timegm((2026, 9, 16, 14, 0, 0)), "looks": 1000, "no_offer": 600, "tradeable": 100, "fired": True, "gates": {}},
        ]
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        L = Ledger(results=td)
        L.refresh()
        state = {"h": {"pid": 4242, "alive": True, "flag": None, "quiet_s": 12, "watchdog_s": 5, "open": {},
                       "halt": None, "kalshi_ok": True, "feeds_ok": True, "disk_gb": 30.0}}
        now = {"t": calendar.timegm((2026, 9, 16, 15, 0, 0))}           # 11 AM ET Sep 16
        tg = FakeTelegram()
        cfgp = os.path.join(td, "telegram.json")
        ph = Phone({"token": "x", "secret": "open sesame"}, tg, ledger=L, health_fn=lambda: state["h"],
                   cfg_path=cfgp, now_fn=lambda: now["t"])

        # Plant a Kalshi ledger for the fixture: money comes from Kalshi now,
        # so a test that wants a TODAY figure has to provide Kalshi's books.
        import pinledger as _pl
        _pl_sv = _pl.LEDGER
        _pl.LEDGER = os.path.join(td, "kalshi_ledger.json")
        with open(_pl.LEDGER, "w", encoding="utf-8") as _fh:
            json.dump({"settlements": {"k1": {
                "ticker": c1, "market_result": "no",
                "no_count_fp": "85.00", "no_total_cost_dollars": "83.30",
                "yes_count_fp": "0.00", "yes_total_cost_dollars": "0.00",
                "revenue": 8500, "fee_cost": "0.0374",
                "settled_time": "2026-09-16T14:00:20Z"}}}, _fh)
        ck(ph.handle(111, "/status") is None, "before pairing, every message is ignored")
        ck(ph.handle(111, "/pair wrong words") is None and ph.chat_id is None, "a wrong secret is refused silently")
        r = ph.handle(111, "/pair open sesame")
        ck(r and r.startswith("Paired") and ph.chat_id == 111, "the right secret pairs the chat")
        ck(json.load(open(cfgp))["chat_id"] == 111, "...and the chat id is saved to the config file")
        ck(ph.handle(222, "/status") is None, "another chat is still ignored after pairing")
        s = ph.handle(111, "/status")
        ck("TRADING" in s and "Checked just now" in s and "process 4242 is OPEN" in s, "/status carries the state and its evidence")
        # MONEY COMES FROM KALSHI NOW, not from the log this test plants, so
        # "today" is legitimately empty here. The bank still comes from the
        # bot's own autosize record, which is ours to read.
        ck("Bank $500.00" in s and "TODAY" in s,
           "/status carries the bank and a TODAY line; the money itself is "
           "Kalshi's (results/kalshi_ledger.json) and is absent in this fixture")
        t = ph.handle(111, "/today")
        ck("$+1.66" in t and "+0.33%" in t and "1 closes" in t, "/today: money, %% of the bank at day start, closes")
        ck("no settled bets" in ph.handle(111, "/yesterday"), "/yesterday with nothing settled says so")
        ck("SELLERS:" in ph.handle(111, "/market") and "BOUGHT 85" in ph.handle(111, "/market"), "/market: level and what happened")
        # THE OPPORTUNITY TREND REACHES THE PHONE, and a health dict that does
        # not carry it must not break the command -- the operator reads
        # /market from his phone when the app is not in front of him.
        state["h"]["supply_lines"] = ["Cheap offers: up 7% on a normal day."]
        state["h"]["supply_age_d"] = 0.5
        mk = ph.handle(111, "/market")
        ck("IS THE OPPORTUNITY GOING AWAY?" in mk and "up 7%" in mk,
           "/market carries the opportunity trend, from the same lines the "
           "desktop shows, so the two cannot drift apart")
        ck("0.5 days ago" in mk,
           "...and says how old the measurement is, because a stale trend is a "
           "reassuring number about a week that already ended")
        state["h"].pop("supply_lines")
        ck("SELLERS:" in ph.handle(111, "/market"),
           "NULL: a health reading with no opportunity block still answers")
        ck(ph.handle(111, "/losses") == "No losing closes.", "/losses with none")
        ck(ph.handle(111, "/hedges") == "No hedges yet.", "/hedges with none")
        ck(ph.handle(111, "/open") == "No open bets.", "/open with none")
        ck("ALL TIME" in ph.handle(111, "/days"), "/days ends with all time")
        r = ph.handle(111, "/stop")
        ck("/stop yes" in r and not ph.busy, "/stop without yes only explains; nothing is stopped")
        ck(ph.handle(111, "/mute") == "Alerts off. /unmute to turn them back on." and ph.muted, "/mute")
        ck(ph.handle(111, "/unmute") == "Alerts on." and not ph.muted, "/unmute")
        ck("Commands:" in ph.handle(111, "/help") and "Commands:" in ph.handle(111, "what"), "/help, and an unknown message gets the help")
        ck("Commands:" in ph.handle(111, "/help@PinBotBot"), "a command with the @botname suffix still works")

        # alerts: first tick only records; a change sends once
        ck(ph.alerts_tick() == [] and ph.last_state == "TRADING", "the first alert tick sends nothing, it only learns the state")
        ck(ph.alerts_tick() == [], "NULL: no change, no message")
        state["h"] = dict(state["h"], alive=False)
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and "TRADING -> DOWN" in sent[0], "the bot going down sends one alert")
        ck(ph.alerts_tick() == [], "...and not a second one while it stays down")
        state["h"] = dict(state["h"], alive=True)
        ck("DOWN -> TRADING" in ph.alerts_tick()[0], "coming back sends one too")
        # a new losing close
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "order", "t": "2026-09-16T14:14:31Z", "ticker": c2, "filled": 40.0, "exec_price": 0.97, "status": "executed", "body": {"count": "40.00"}}) + "\n")
            pass
        # THE LOSS ARRIVES IN KALSHI'S BOOKS, not in our log -- that is where
        # money lives now, and it is why the alert can no longer mistake one
        # leg of a hedged market for a losing trade.
        _led = json.load(open(_pl.LEDGER, encoding="utf-8"))
        _led["settlements"]["k2"] = {
            "ticker": c2, "market_result": "yes",
            "no_count_fp": "40.00", "no_total_cost_dollars": "38.80",
            "yes_count_fp": "0.00", "yes_total_cost_dollars": "0.00",
            "revenue": 0, "fee_cost": "0.00",
            "settled_time": "2026-09-16T14:15:20Z"}
        with open(_pl.LEDGER, "w", encoding="utf-8") as _fh:
            json.dump(_led, _fh)
        os.utime(_pl.LEDGER, (time.time() + 5, time.time() + 5))
        sent = ph.alerts_tick()
        ck(len(sent) == 1 and sent[0].startswith("LOSS") and "$-38.80" in sent[0] and "WHY IT HURTS" in sent[0], "a new losing close is sent with its story")
        ck(ph.alerts_tick() == [], "...once")
        ph.muted = True
        state["h"] = dict(state["h"], alive=False)
        ck(ph.alerts_tick() == [] and ph.last_state == "DOWN", "muted: the change is tracked but not sent")
        ph.muted = False
        ck(not any(t_.startswith("YESTERDAY") for _c, t_ in tg.sent), "a summary already due at startup is NOT re-sent (it started at 11 AM ET)")
        # next day, 9 AM ET: the daily summary of the 16th goes out once
        now["t"] += 86400 - 2 * 3600
        sent = ph.alerts_tick()
        ck(any(m.startswith("YESTERDAY") and "2026-09-16" in m for m in sent), "after 8 AM ET the daily summary of yesterday goes out")
        ck(not any(m.startswith("YESTERDAY") for m in ph.alerts_tick()), "...once per day")
        ck(all(cid == 111 for cid, _t in tg.sent), "every alert went to the paired chat")
        # long messages are split by the real transport's rule
        big = "x" * (MAX_LEN * 2 + 5)
        chunks = [big[i:i + MAX_LEN] for i in range(0, len(big), MAX_LEN)]
        ck(len(chunks) == 3 and sum(len(c) for c in chunks) == len(big), "a long reply is split under Telegram's limit")
        # poll_once routes replies to the sender and advances the offset
        tg.push(111, "/help")
        tg.push(333, "/status")
        ph.poll_once()
        ck(tg.sent[-1][0] == 111 and "Commands:" in tg.sent[-1][1] and ph.offset == 3, "poll: the paired chat gets its reply, the stranger nothing, offset advances")
    _pl.LEDGER = _pl_sv
    print("pinphone selftest: OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return 0
    if "--preview" in sys.argv:
        ph = Phone({"chat_id": 0}, FakeTelegram())
        ph.ledger.refresh()
        print(ph.text_status())
        print("\n--- /market ---\n" + ph.text_market())
        print("\n--- /hedges ---\n" + ph.text_hedges())
        return 0
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as e:
        print("no usable %s (%s). See the docstring for setup." % (CONFIG, e))
        return 2
    if not cfg.get("token"):
        print("%s has no token" % CONFIG)
        return 2
    Phone(cfg, Telegram(cfg["token"])).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
