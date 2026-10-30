"""/pause /start /stop -- the trading controls. The ONLY module of the phone that calls pindesk's start / pause / stop.

v-tg-rebuild step 9 (2026-10-30): Phone.control and the /pause /start /stop branches of Phone.handle as a command module,
byte-identical (golden shadow, with pindesk's controls stubbed: the harness never runs the real ones).

How a control runs (unchanged): the reply comes at once (CONTROL_REPLY); the work runs on a daemon thread that reports
each step through ctx.say ('pause: ...'), sleeps 3 s, then sends the /status page; any failure is said ('stop failed:
...') and logged. While one runs, `busy` (ctx.state.busy: the Phone until step 11; an unlocked flag, as before) makes
another control answer 'Still working on the last command.'. /stop alone only explains (STOP_ASK); '/stop yes' stops.
HAZARD KEPT (DESIGN 1.1): /start means 'trade again', and Telegram clients send /start when a chat is first opened; only
the paired chat is answered, so this is mitigated -- do not change it silently.

v-tg-step12 (2026-10-30, lane R): ONE bot by name. '/pause <bot>' and '/start <bot>' for any bot but the pin bot go to
phone/commands/botctl.py (its stop file, asked first; /resume and /play are declared there). Plain /pause and /start,
and '/pause pin' / '/start pin', are the pin bot's controls exactly as before. A word after /pause or /start that names
no bot ('/pause now') used to pause / start the pin bot; it now answers 'No bot is called ...' and changes nothing.
"""
import importlib
import threading
import time
import traceback

import pindesk
from phone.command import Command, by_name, declare
from phone.html import Html
from phone.log import log

# from pinphone.CONTROL_REPLY / STOP_ASK (only the controls answer with them; test_controls checks they still match)
CONTROL_REPLY = {"start": Html("▶️ <b>Starting…</b>"),
                 "pause": Html("⏸ <b>Pausing</b>: no new bets; waiting for open ones to settle…"),
                 "stop": Html("⏹ <b>Stopping now…</b>"),
                 "busy": Html("⏳ Still working on the last command.")}
STOP_ASK = Html("⚠️ <b>STOP stops right now</b>, even with a bet open (it settles by itself but will not be "
                "hedged).\nTo confirm, send:  <code>/stop yes</code>\nOr use /pause to finish open bets first.")
STATUS_MODULE = "phone.commands.status"        # lane D1's /status module


def status_reply(ctx):
    """The /status page the worker sends when the work is done (Phone.control: self.text_status()): D1's /status Command
    (Command.run is text_status, its error wall included). v-tg-rebuild step 10: Phone.text_status is gone, so there is
    no fallback; a /status module that cannot be imported raises here and the worker says '<which> failed: ...'."""
    importlib.import_module(STATUS_MODULE)
    com = by_name("/status")
    if com is None:
        raise RuntimeError("no /status command is declared")
    return com.run(ctx.with_message("/status"))


def control(ctx, which):
    """Phone.control(which), verbatim: 'start', 'pause' or 'stop'."""
    st = ctx.state
    if st.busy:
        return CONTROL_REPLY["busy"]
    st.busy = True

    def worker():
        try:
            if which == "start":
                pindesk.do_start(lambda m: ctx.say("start: " + m))
            elif which == "pause":
                pindesk.do_pause(lambda m: ctx.say("pause: " + m), lambda s: ctx.say(s))
            elif which == "stop":
                pindesk.do_stop(lambda m: ctx.say("stop: " + m))
            time.sleep(3)
            ctx.say(status_reply(ctx))
        except Exception as e:                        # noqa: BLE001
            ctx.say("%s failed: %s" % (which, e))
            log(traceback.format_exc())
        finally:
            st.busy = False
    threading.Thread(target=worker, daemon=True).start()
    return CONTROL_REPLY[which]


def _other_bot(ctx):
    """True when the message names a bot other than the pin bot ('/pause jb', '/start fx yes', '/pause now')."""
    words = ctx.arg.split()
    return bool(words) and words[0].lower().lstrip("/") != "pin"


def pause(ctx):
    if _other_bot(ctx):
        from phone.commands import botctl
        return botctl.pause_cmd(ctx)
    return control(ctx, "pause")


def start(ctx):
    if _other_bot(ctx):
        from phone.commands import botctl
        return botctl.resume_cmd(ctx)
    return control(ctx, "start")


def stop(ctx):
    if ctx.arg.strip().lower() == "yes":
        return control(ctx, "stop")
    return STOP_ASK


COMMANDS = declare(
    Command(names=("/pause",), section="controls", order=10, help_line="/pause — no new bets, wait for open ones, then stop",
            chart=None, handle=pause, runs_in_worker=True, examples=("/pause jb", "/pause now", "/pause pin")),
    Command(names=("/start",), section="controls", order=20, help_line="/start — trade again",
            chart=None, handle=start, runs_in_worker=True, examples=("/start@kalsbot", "/start@")),
    Command(names=("/stop",), section="controls", order=30, help_line="<code>/stop yes</code> — stop right now",
            chart=None, handle=stop, runs_in_worker=True, examples=("/stop yes", "/stop no", "/stop YES")))
